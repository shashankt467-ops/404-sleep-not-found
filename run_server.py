import os
import sys
import uvicorn

# Configure python path to find backend modules
root_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(root_dir, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

if __name__ == "__main__":
    print("================================================================")
    print("  HC-04 Emergency Information Interoperability Gateway")
    print("================================================================")
    print("  * Frontend & App Console:  http://localhost:8000/ or http://127.0.0.1:8000/")
    print("  * OpenAPI Specification:   http://localhost:8000/openapi.json")
    print("================================================================")
    port = int(os.getenv("PORT", 8000))
    is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production" or os.getenv("RAILWAY_ENVIRONMENT") is not None
    print(f"  * Starting on port {port} (production={is_prod})...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, app_dir=backend_dir, reload=not is_prod, reload_dirs=[backend_dir] if not is_prod else None)

