from __future__ import annotations

import mimetypes
import os
from pathlib import Path


class S3ObjectStorage:
    def __init__(self, bucket=None, client=None):
        self.bucket = bucket or os.environ["S3_BUCKET"]
        if client is None:
            import boto3

            client = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
        self.client = client

    def upload(self, key: str, source: Path, *, public: bool = False) -> str:
        if not public and key.startswith("episodes/") and "/drafts/" not in key:
            raise ValueError("private artifacts must use a drafts prefix")
        extra = {"ContentType": mimetypes.guess_type(source.name)[0] or "application/octet-stream"}
        self.client.upload_file(str(source), self.bucket, key, ExtraArgs=extra)
        return (
            f"https://{self.bucket}.s3.{os.getenv('AWS_REGION', 'us-east-1')}.amazonaws.com/{key}"
        )


class DynamoRepository:
    """Single-table repository: PK identifies aggregate; SK identifies version/entity."""

    def __init__(self, table=None):
        if table is None:
            import boto3

            table = boto3.resource(
                "dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1")
            ).Table(os.environ["DYNAMODB_TABLE"])
        self.table = table

    def acquire_lock(self, week: str, run_id: str, expires: int) -> None:
        self.table.put_item(
            Item={"PK": f"LOCK#{week}", "SK": "LOCK", "run_id": run_id, "expires": expires},
            ConditionExpression="attribute_not_exists(PK) OR expires < :now",
            ExpressionAttributeValues={":now": int(__import__("time").time())},
        )

    def save_papers(self, papers: list[dict]) -> None:
        with self.table.batch_writer(overwrite_by_pkeys=["PK", "SK"]) as batch:
            for paper in papers:
                batch.put_item(
                    Item={
                        "PK": f"PAPER#{paper['arxiv_id']}",
                        "SK": f"VERSION#{paper['version']:04d}",
                        **paper,
                    }
                )

    def publish_atomic(self, episode: dict) -> None:
        if episode.get("status") != "published":
            raise ValueError("only published episodes can move the public pointer")
        self.table.meta.client.transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": self.table.name,
                        "Item": {
                            "PK": {"S": f"EPISODE#{episode['week']}"},
                            "SK": {"S": "METADATA"},
                            "payload": {"S": __import__("json").dumps(episode)},
                        },
                    }
                },
                {
                    "Put": {
                        "TableName": self.table.name,
                        "Item": {
                            "PK": {"S": "PUBLICATION"},
                            "SK": {"S": "CURRENT"},
                            "week": {"S": episode["week"]},
                        },
                    }
                },
            ]
        )
