# EduPilot AI — MVP

A local, self-contained academic support platform built with Python's standard library, SQLite, HTML, CSS and vanilla JavaScript.

## Run on Linux Mint

1. Extract the ZIP.
2. Open a terminal in the `EduPilot_AI` folder.
3. Run:

   ```bash
   python3 app.py
   ```

4. Open http://localhost:8000 in your browser.
5. Stop the server with `Ctrl+C`.

No Python packages are required for the core MVP.

## Included features

- Academic profile: university, degree, branch, year, semester, regulation and daily study time.
- Local syllabus catalogue lookup for the included **Demo Technical University** sample curriculum.
- Structured syllabus JSON upload.
- Subject-wise academic record entry.
- Explainable rule-based performance estimates:
  - Marks: 35%
  - Internal assessments: 25%
  - Assignments: 20%
  - Attendance: 20%
- Personalized study-plan generation, prioritizing lower-scoring subjects and unassessed topics.
- Task completion tracking.
- Syllabus-grounded tutor fallback with lessons and practice prompts.
- Optional OpenAI-compatible chat-completions API integration.
- Topic mastery tracking after learner self-assessment.
- SQLite persistence in `edupilot.db`.

## Optional LLM tutor

The built-in tutor works without an API key using the lesson and question material in the syllabus catalogue.

To enable generated conversational teaching, set environment variables before launching:

```bash
export OPENAI_API_KEY="your_api_key"
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4o-mini"
python3 app.py
```

The API key is read only by the Python server. Never place it in `static/script.js` or HTML.

## Custom syllabus JSON format

Use a JSON file with a top-level `subjects` array:

```json
{
  "subjects": [
    {
      "code": "CS301",
      "name": "Example Subject",
      "units": [
        {
          "title": "Unit 1 — Foundations",
          "topics": ["Topic A", "Topic B"],
          "lesson": "A concise explanation of this unit.",
          "questions": [
            "Explain Topic A.",
            "Give an example of Topic B."
          ]
        }
      ]
    }
  ]
}
```

Upload it from **My syllabus → Upload syllabus JSON**.

## Important limitations of this MVP

- The bundled university catalogue is a demonstration curriculum, not a verified feed from a real university. Students should confirm it against their official curriculum.
- Automatic live retrieval from arbitrary university websites is not included. The MVP uses its local catalogue or a student-supplied structured JSON syllabus.
- The tutor's built-in fallback is syllabus-based, not a generative LLM. Configure an API key for LLM-generated teaching.
- Topic mastery is currently updated from the student's self-assessment after practice; it is an estimate, not a validated psychometric measurement.
- Prediction is a transparent weighted rule-based estimate, not a trained machine-learning model and not a guarantee of exam results.
- Authentication and multi-user accounts are not included. This local MVP is designed for a single-user demonstration.

## Data and reset

- Student data is stored in `edupilot.db`.
- To reset the local demo, stop the server and delete `edupilot.db`. The sample syllabus catalogue will be recreated at startup.
- Do not commit real student records or API keys to source control.
