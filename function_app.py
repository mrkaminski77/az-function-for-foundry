import azure.durable_functions as df
import azure.functions as func
from src.ocds_routes import ocds_blueprint
from src.ocds_durable import ocds_durable_blueprint
from src.connectivity_routes import connectivity_blueprint
from src.timer_function import timer_blueprint
from src.table_storage_routes import table_storage_blueprint

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)
app.register_functions(ocds_blueprint)
app.register_functions(ocds_durable_blueprint)
app.register_functions(connectivity_blueprint)
app.register_functions(timer_blueprint)
app.register_functions(table_storage_blueprint)

