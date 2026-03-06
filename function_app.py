import azure.functions as func
from src.ocds_routes import ocds_blueprint
from src.connectivity_routes import connectivity_blueprint
from src.timer_function import timer_blueprint

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
app.register_functions(ocds_blueprint)
app.register_functions(connectivity_blueprint)
app.register_functions(timer_blueprint)

