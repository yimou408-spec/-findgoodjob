def route_task(task: str) -> str:
    t = task.lower()
    if "analy" in t or "jd" in t:
        return "jd_analysis"
    if "resume" in t or "rewrite" in t:
        return "resume_rewrite"
    return "general"
