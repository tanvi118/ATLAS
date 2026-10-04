import json
import random
from datetime import date, timedelta
from pathlib import Path


OUTPUT_FILE = Path(
    "rag/data/raw/synthetic/synthetic_student_tasks.json"
)

subjects = [
    "Machine Learning",
    "Deep Learning",
    "NLP",
    "Data Structures",
    "Database Management",
    "Computer Networks",
    "Compiler Design",
    "Operating Systems",
]

task_names = [
    "Complete assignment",
    "Prepare lecture notes",
    "Solve practice questions",
    "Prepare for quiz",
    "Complete lab work",
    "Revise previous topics",
    "Prepare presentation",
    "Complete project work",
]

priorities = ["low", "medium", "high"]
difficulties = ["easy", "medium", "hard"]
statuses = ["pending", "in_progress", "completed"]


# Synthetic SAP IDs for our demo data
SAP_IDS = [
    str(500121478 + i)
    for i in range(100)
]


def generate_tasks(number_of_tasks=500):
    tasks = []

    start_date = date.today()

    for i in range(1, number_of_tasks + 1):

        deadline = start_date + timedelta(
            days=random.randint(1, 30)
        )

        task = {
            "sap_id": random.choice(SAP_IDS),
            "task": random.choice(task_names),
            "subject": random.choice(subjects),
            "deadline": deadline.isoformat(),
            "priority": random.choice(priorities),
            "difficulty": random.choice(difficulties),
            "status": random.choice(statuses),
            "estimated_time": random.randint(30, 180),
        }

        tasks.append(task)

    return tasks


def main():
    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    tasks = generate_tasks(500)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            tasks,
            file,
            indent=2
        )

    print(f"Created {len(tasks)} synthetic tasks.")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()