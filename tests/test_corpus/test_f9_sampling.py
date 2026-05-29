import csv
import json
import sqlite3

from scripts.corpus.f9_sampling import (
    BLIND_COLUMNS,
    F4_HOLDOUT_COLUMNS,
    export_f9_annotation_package,
    load_candidate_rows,
)


def _create_db(path):
    con = sqlite3.connect(path)
    con.executescript(
        """
        create table turns (
            id integer primary key,
            session_id text not null,
            user_message text not null,
            assistant_message text not null,
            status text not null,
            scenario text,
            created_at text not null
        );
        create table candidates (
            id integer primary key,
            turn_id integer not null,
            candidate_id text not null,
            orientation text not null,
            text text not null,
            epitome_er integer not null,
            epitome_ip integer not null,
            epitome_ex integer not null,
            boundary_flag boolean not null,
            boundary_reason text not null,
            weighted_total float not null,
            created_at text not null
        );
        """
    )
    return con


def _insert_turn(con, turn_id, session_id, scenario, user_message, assistant_message):
    con.execute(
        """
        insert into turns (
            id, session_id, user_message, assistant_message, status, scenario, created_at
        ) values (?, ?, ?, ?, 'answered', ?, ?)
        """,
        (
            turn_id,
            session_id,
            user_message,
            assistant_message,
            scenario,
            f"2026-05-25T00:{turn_id:02d}:00",
        ),
    )


def _insert_candidate(
    con,
    candidate_id,
    turn_id,
    orientation,
    weighted_total,
    er,
    ip,
    ex,
):
    con.execute(
        """
        insert into candidates (
            id, turn_id, candidate_id, orientation, text, epitome_er, epitome_ip,
            epitome_ex, boundary_flag, boundary_reason, weighted_total, created_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, 0, '', ?, ?)
        """,
        (
            candidate_id,
            turn_id,
            f"c{candidate_id}",
            orientation,
            f"候选回复 {candidate_id}",
            er,
            ip,
            ex,
            weighted_total,
            f"2026-05-25T01:{candidate_id:02d}:00",
        ),
    )


def _seed_candidates(path):
    con = _create_db(path)
    next_turn_id = 1
    next_candidate_id = 1
    scenarios = ["学业压力", "同伴关系", "亲子摩擦"]
    orientations = ["情感共情型", "认知共情型"]
    scores = [3.2, 4.6, 6.7]
    for scenario in scenarios:
        for score in scores:
            for orientation in orientations:
                _insert_turn(
                    con,
                    next_turn_id,
                    f"real-llm-20260522-215717-s{next_turn_id}",
                    scenario,
                    f"{scenario} 倾诉 {next_turn_id}",
                    f"{scenario} 已选回复 {next_turn_id}",
                )
                _insert_candidate(
                    con,
                    next_candidate_id,
                    next_turn_id,
                    orientation,
                    score,
                    er=next_candidate_id % 3,
                    ip=(next_candidate_id + 1) % 3,
                    ex=(next_candidate_id + 2) % 3,
                )
                next_turn_id += 1
                next_candidate_id += 1
    con.commit()
    con.close()


def test_load_candidate_rows_builds_prior_turn_history(tmp_path):
    db_path = tmp_path / "history.sqlite"
    con = _create_db(db_path)
    _insert_turn(con, 1, "real-llm-session-1", "学业压力", "第一次倾诉", "第一次回复")
    _insert_turn(con, 2, "real-llm-session-1", "学业压力", "第二次倾诉", "第二次回复")
    _insert_candidate(con, 1, 2, "情感共情型", 4.5, er=2, ip=1, ex=2)
    con.commit()
    con.close()

    rows = load_candidate_rows(db_path, session_prefixes=["real-llm"])

    assert len(rows) == 1
    assert json.loads(rows[0].history) == [
        {"role": "student", "text": "第一次倾诉"},
        {"role": "assistant", "text": "第一次回复"},
    ]


def test_export_f9_annotation_package_writes_blind_and_holdout_files(tmp_path):
    db_path = tmp_path / "local.sqlite"
    _seed_candidates(db_path)
    output_dir = tmp_path / "f9"

    result = export_f9_annotation_package(
        database_path=db_path,
        output_dir=output_dir,
        sample_size=12,
        seed=20260525,
        session_prefixes=["real-llm-20260522-215717"],
    )

    blind_rows = list(
        csv.DictReader(result.blind_annotation_path.open(encoding="utf-8-sig"))
    )
    holdout_rows = list(
        csv.DictReader(result.f4_holdout_path.open(encoding="utf-8-sig"))
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert result.sample_count == 12
    assert result.blind_annotation_path.name == "f9_blind_annotation.csv"
    assert result.f4_holdout_path.name == "f9_f4_scores_holdout.csv"
    assert list(blind_rows[0].keys()) == BLIND_COLUMNS
    assert list(holdout_rows[0].keys()) == F4_HOLDOUT_COLUMNS
    assert len(blind_rows) == 12
    assert len(holdout_rows) == 12
    assert set(row["sample_no"] for row in blind_rows) == set(
        row["sample_no"] for row in holdout_rows
    )
    assert all(row["A_ER"] == "" and row["B_EX"] == "" for row in blind_rows)
    assert "F4_ER" not in blind_rows[0]
    assert "weighted_total" not in blind_rows[0]
    assert manifest["seed"] == 20260525
    assert manifest["sample_size"] == 12
    assert manifest["source_candidate_count"] == 18


def test_export_f9_annotation_package_is_deterministic_for_same_seed(tmp_path):
    db_path = tmp_path / "local.sqlite"
    _seed_candidates(db_path)

    first = export_f9_annotation_package(
        database_path=db_path,
        output_dir=tmp_path / "first",
        sample_size=9,
        seed=7,
        session_prefixes=["real-llm-20260522-215717"],
    )
    second = export_f9_annotation_package(
        database_path=db_path,
        output_dir=tmp_path / "second",
        sample_size=9,
        seed=7,
        session_prefixes=["real-llm-20260522-215717"],
    )

    assert first.blind_annotation_path.read_text(
        encoding="utf-8-sig"
    ) == second.blind_annotation_path.read_text(encoding="utf-8-sig")
    assert first.f4_holdout_path.read_text(
        encoding="utf-8-sig"
    ) == second.f4_holdout_path.read_text(encoding="utf-8-sig")
