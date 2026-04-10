from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes.simulate import router as simulate_router
from .routes.register_circuit import router as register_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Analog CircuitSimulation API (OpAmp)",
        description="Wrap SimulationAPI from CircuitCollector as a FastAPI service",
        version="0.1.0",
    )

    # CORS (adjust according to needs)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    def health():
        return {"status": "ok"}

    # register routes
    app.include_router(simulate_router)
    app.include_router(register_router)
    return app


app = create_app()
