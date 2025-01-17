import uvicorn
from pathlib import Path
import yaml
from src.main import ConfigManager

def run_dev_server():
    # Load configuration
    config_path = Path("src/config/default.yml")
    try:
        config = ConfigManager.load_config(str(config_path))
        
        # Get host and port from config, or use defaults
        host = config.get('api', {}).get('host', '127.0.0.1')
        port = config.get('api', {}).get('port', 8000)
        
        # Run development server with hot reload
        uvicorn.run(
            "src.main:IoTGatewayApp(str(Path('src/config/default.yml'))).api_server.app",
            host=host,
            port=port,
            reload=True,
            reload_dirs=['src/iot_gateway'],
            workers=1
        )
    except Exception as e:
        print(f"Failed to start development server: {e}")
        raise

if __name__ == "__main__":
    run_dev_server()