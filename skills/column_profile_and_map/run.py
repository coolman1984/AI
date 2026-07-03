"""SK-002 column-profile-and-map: profile columns and propose canonical mapping."""



def run_profile_and_map(
    table_name: str,
    duckdb_con=None,
    db_registry=None,
    prior_mapping: dict = None,
) -> dict:
    """Profile columns from a staged DuckDB table and propose a canonical mapping.

    Args:
        table_name: Name of the staged DuckDB table to profile.
        duckdb_con: DuckDB connection (if None, tries to get one).
        db_registry: FOREMAN registry DB connection.
        prior_mapping: Optional dict of {source_column: canonical_name} from a
                       previous mapping for a similar dataset.

    Returns:
        dict with profile results and mapping proposal.
    """
    if duckdb_con is None:
        try:
            from engines.data.ingest import get_connection
            duckdb_con = get_connection()
        except Exception as e:
            return {
                "status": "failed",
                "error": f"Cannot connect to DuckDB: {e}",
            }

    try:
        # Verify table exists
        try:
            columns_info = duckdb_con.execute(
                f"DESCRIBE {table_name}"
            ).fetchall()
        except Exception:
            return {
                "status": "failed",
                "error": f"Table '{table_name}' not found. Run SK-001 first.",
            }

        col_names = [row[0] for row in columns_info]

        # Get sample rows for type inference
        sample_rows = duckdb_con.execute(
            f"SELECT * FROM {table_name} LIMIT 100"
        ).fetchall()
        col_count = len(col_names)
        row_dicts = [
            {col_names[i]: (str(row[i]) if row[i] is not None else None)
             for i in range(col_count)}
            for row in sample_rows
        ]

        # Infer types
        from engines.data.types import infer_column_types
        type_map = infer_column_types(col_names, row_dicts)

        # Build profile
        profile = []
        for col in col_names:
            field_info = type_map.get(col, {})
            dtype = field_info.get("python_type", "unknown") if isinstance(field_info, dict) else str(field_info)
            profile.append({
                "column": col,
                "inferred_type": dtype,
                "null_count": sum(1 for r in row_dicts if r.get(col) is None),
                "sample_values": [r.get(col) for r in row_dicts[:5] if r.get(col) is not None][:3],
                "suspected_key": "id" in col.lower() or "code" in col.lower(),
            })

        # Propose mapping
        mapping_proposal = {}
        if prior_mapping:
            for src_col in col_names:
                if src_col in prior_mapping:
                    mapping_proposal[src_col] = prior_mapping[src_col]
                else:
                    mapping_proposal[src_col] = src_col.lower().replace(" ", "_")
        else:
            for col in col_names:
                mapping_proposal[col] = col.lower().replace(" ", "_")

        return {
            "status": "done",
            "table": table_name,
            "column_count": len(col_names),
            "profile": profile,
            "mapping_proposal": mapping_proposal,
            "requires_confirmation": prior_mapping is None,
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": f"Profile and map failed: {e}",
        }
