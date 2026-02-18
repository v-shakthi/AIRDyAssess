"""
main.py — Start the AI Readiness Advisor API server.

Usage:
    python main.py              # Start on port 8000
    python main.py --port 9000
    python main.py --reload     # Dev mode

Then in a separate terminal:
    streamlit run dashboard/app.py
"""

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="AI Readiness Advisor API")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    print(f"""
╔══════════════════════════════════════════════════════════╗
║          AI Readiness & Migration Advisor v1.0          ║
║    Multi-doc RAG · Scored Assessment · PDF Reports      ║
╠══════════════════════════════════════════════════════════╣
║  API:        http://localhost:{args.port}                   ║
║  API Docs:   http://localhost:{args.port}/docs               ║
║  Dashboard:  streamlit run dashboard/app.py              ║
║  API Key:    sk-advisor-demo-001                         ║
╚══════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
