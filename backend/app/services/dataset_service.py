"""Dataset service: upload/persist via ObjectStorage + business DB."""

import json
from uuid import uuid4

from loguru import logger

from app.models import Dataset
from app.schemas.dataset import DatasetInfo
from app.storage.database import SessionLocal
from app.storage.object_store import get_object_storage
from app.tools.data.loader import dataset_file_key, load_dataframe


class DatasetService:
    def save_upload(self, filename: str, content: bytes, name: str | None = None) -> DatasetInfo:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "csv"
        if ext not in ("csv", "xlsx", "xls", "json"):
            raise ValueError(f"unsupported file type: {ext}")

        storage = get_object_storage()
        dataset_id = f"ds_{uuid4().hex[:10]}"
        key = dataset_file_key(dataset_id, ext)
        storage.save(key, content)

        df = load_dataframe(dataset_id, ext)
        info = DatasetInfo(
            id=dataset_id,
            filename=filename,
            name=name or filename,
            source_type="file",
            row_count=int(len(df)),
            column_count=int(df.shape[1]),
        )
        with SessionLocal() as session:
            session.add(
                Dataset(
                    id=info.id,
                    filename=filename,
                    name=info.name,
                    source_type="file",
                    storage_path=key,
                    row_count=info.row_count,
                    column_count=info.column_count,
                )
            )
            session.commit()
        logger.info(f"dataset saved: {info.id} ({filename}, {info.row_count} rows)")
        return info

    def get_info(self, dataset_id: str) -> DatasetInfo | None:
        with SessionLocal() as session:
            row = session.get(Dataset, dataset_id)
            if row is None:
                return None
            return DatasetInfo(
                id=row.id,
                filename=row.filename,
                name=row.name or "",
                source_type=row.source_type,
                row_count=row.row_count,
                column_count=row.column_count,
            )

    def save_dataframe(self, filename: str, df, source_type: str = "file", name: str | None = None) -> DatasetInfo:
        """Persist an already-parsed DataFrame (used by web sources)."""
        dataset_id = f"ds_{uuid4().hex[:10]}"
        key = dataset_file_key(dataset_id, "csv")
        get_object_storage().save(key, df.to_csv(index=False).encode("utf-8-sig"))
        with SessionLocal() as session:
            session.add(
                Dataset(
                    id=dataset_id,
                    filename=filename,
                    name=name or filename,
                    source_type=source_type,
                    storage_path=key,
                    row_count=int(len(df)),
                    column_count=int(df.shape[1]),
                )
            )
            session.commit()
        logger.info(f"dataframe saved: {dataset_id} ({filename}, {len(df)} rows, source={source_type})")
        info = self.get_info(dataset_id)
        assert info is not None
        return info

    def register_database(self, conn_params: dict, table: str, name: str) -> DatasetInfo:
        """Register a database table as a virtual dataset (READ ONLY).

        Connection params are stored in storage_path (JSON) — for local demo;
        production should store only a secret-managed connection reference.
        """
        dataset_id = f"ds_{uuid4().hex[:10]}"
        storage_path = json.dumps({"connection": conn_params, "table": table}, ensure_ascii=False)
        with SessionLocal() as session:
            session.add(
                Dataset(
                    id=dataset_id,
                    filename=name,
                    name=name,
                    source_type="database",
                    storage_path=storage_path,
                )
            )
            session.commit()
        logger.info(f"database dataset registered: {dataset_id} ({table})")
        info = self.get_info(dataset_id)
        assert info is not None
        return info

    def get_database_source(self, dataset_id: str) -> dict | None:
        """Return {connection, table} for a database-backed dataset, or None."""
        with SessionLocal() as session:
            row = session.get(Dataset, dataset_id)
            if row is None or row.source_type != "database":
                return None
            return json.loads(row.storage_path)

    def get_ext(self, dataset_id: str) -> str:
        with SessionLocal() as session:
            row = session.get(Dataset, dataset_id)
            if row is None or not row.storage_path:
                return "csv"
            if row.source_type == "database":
                return "csv"  # database sources carry no file extension
            return row.storage_path.rsplit(".", 1)[-1].lower()


__all__ = ["DatasetService"]
