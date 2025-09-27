.PHONY: run dev


run:
uvicorn api.app:app --reload --port 8000


# simple end-to-end
# 1) start server: make run
# 2) ingest: curl -X POST localhost:8000/ingest -H 'Content-Type: application/json' -d '{"text":"In 2024, revenue grew 12%. Also, this is the best year ever."}'
# 3) analyze: curl -X POST localhost:8000/analyze -H 'Content-Type: application/json' -d '{"ingest_id":"<returned-id>"}'
# 4) status: curl 'localhost:8000/status?job_id=<job>'
# 5) results: curl 'localhost:8000/results?job_id=<job>'