import json
from pathlib import Path

from app.database import SessionLocal, init_db
from app.schemas import JobCreate
from app.services.jd_service import analyze_job, create_job
from app.services.resume_service import revise_resume_for_job


def run_demo() -> None:
    example_path = Path(__file__).with_name("example.json")
    example = json.loads(example_path.read_text(encoding="utf-8"))

    job_payload = JobCreate(**example["create_job_request"])
    resume_text = example["revise_resume_request"]["resume_text"]

    init_db()
    db = SessionLocal()
    try:
        job = create_job(db, job_payload)
        analysis = analyze_job(db, job)
        revised_resume = revise_resume_for_job(job, resume_text)
    finally:
        db.close()

    print("=" * 80)
    print("FindGoodJob Demo")
    print("=" * 80)
    print(f"岗位 ID: {job.id}")
    print(f"岗位名称: {job.title}")
    print(f"公司: {job.company}")
    print("\n[岗位分析结果]")
    print(analysis)
    print("\n[简历修订结果]")
    print(revised_resume)


if __name__ == "__main__":
    run_demo()
