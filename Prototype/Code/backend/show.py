import inspect
from app.orchestrator.gemini_router import Orchestrator
print('CLASSIFY SOURCE\n'+inspect.getsource(Orchestrator.classify))
print('RUN_TOOLS SOURCE\n'+inspect.getsource(Orchestrator.run_tools))
