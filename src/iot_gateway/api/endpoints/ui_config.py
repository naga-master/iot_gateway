from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import psutil
import subprocess
import speedtest
from ...utils.logging import get_logger
from fastapi.templating import Jinja2Templates
import datetime
import time
import os
import zipfile
import io
import re
from ...utils.wifi_manager import WiFiManager


logger = get_logger(__name__)

ui_config_router = APIRouter()
templates = Jinja2Templates(directory="src/templates")
wifi_manager = WiFiManager()


@ui_config_router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint that renders the main dashboard"""
    try:
        system_info = get_system_info()
        # Get initial WiFi information
        wifi_info = wifi_manager.get_current_wifi_info()
        networks = wifi_manager.scan_networks()
        
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "system_info": system_info,
                "wifi_info": wifi_info,
                "networks": networks
            }
        )
    except Exception as e:
        logger.error(f"Error rendering dashboard: {e}")
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "system_info": get_system_info(),
                "wifi_info": {},
                "networks": []
            }
        )

@ui_config_router.get("/api/metrics/cpu")
async def get_cpu_usage():
    return {"usage": psutil.cpu_percent()}


# Need to fix it throws 500 error in inspect element for every 5s
@ui_config_router.get("/api/system-info")
async def sys_info():
    """Return only the system information"""
    try:
        return get_system_info()
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        

def get_system_info():
    """Gather all system information"""
    try:
        # Get CPU temperature
        try:
            temp = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
            temperature = float(temp.replace("temp=", "").replace("'C", ""))
        except:
            temperature = 0  # Fallback if temperature can't be read

        # Calculate uptime
        uptime_seconds = time.time() - psutil.boot_time()
        
        uptime = str(datetime.timedelta(seconds=int(uptime_seconds)))

        # Get memory usage
        memory = psutil.virtual_memory()
        
        return {
            "version": "1.0.0",  # Replace with actual version tracking
            "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "uptime": uptime,
            "status": "Running",
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": memory.percent,
            "temperature": temperature
        }
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return {}

@ui_config_router.get("/api/metrics/memory")
async def get_memory_usage():
    memory = psutil.virtual_memory()
    return {
        "total": memory.total,
        "used": memory.used,
        "percent": memory.percent
    }

@ui_config_router.get("/api/metrics/temperature")
async def get_temperature():
    try:
        temp = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
        return {"temperature": float(temp.replace("temp=", "").replace("'C", ""))}
    except:
        raise HTTPException(status_code=500, detail="Could not read temperature")

@ui_config_router.get("/api/network/info")
async def get_network_info():
    try:
        st = speedtest.Speedtest()
        download_speed = st.download() / 1_000_000  # Convert to Mbps
        upload_speed = st.upload() / 1_000_000  # Convert to Mbps
        
        # Get current WiFi info
        wifi_info = subprocess.check_output(["iwconfig", "wlan0"]).decode()
        
        return {
            "ssid": wifi_info.split('ESSID:"')[1].split('"')[0],
            "signal_strength": wifi_info.split("Signal level=")[1].split(" ")[0],
            "download_speed": f"{download_speed:.1f} Mbps",
            "upload_speed": f"{upload_speed:.1f} Mbps"
        }
    except Exception as e:
        logger.error(f"Error getting network info: {str(e)}")
        raise HTTPException(status_code=500, detail="Could not get network information")

@ui_config_router.post("/api/wifi/connect")
async def connect_wifi(ssid: str = Form(...), password: str = Form(...)):
    """Connect to WiFi network"""
    try:
        success = wifi_manager.connect_to_network(ssid, password)
        if success:
            return JSONResponse(content={"status": "success", "message": "Connected successfully"})
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Failed to connect to network"}
        )
    except Exception as e:
        logger.error(f"Error connecting to network: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@ui_config_router.get("/config", response_class=HTMLResponse)
async def wifi_config(request: Request):
    """Render WiFi configuration page"""
    wifi_info = wifi_manager.get_current_wifi_info()
    networks = wifi_manager.scan_networks()
    return templates.TemplateResponse("partials/wifi_config.html", {
        "request": request,
        "wifi_info": wifi_info,
        "networks": networks
    })

@ui_config_router.get("/api/wifi/status", response_class=HTMLResponse)
async def wifi_status(request: Request):
    """Get current WiFi status"""
    try:
        wifi_info = wifi_manager.get_current_wifi_info()
        return templates.TemplateResponse(
            "partials/wifi_status.html",
            {
                "request": request,
                "wifi_info": wifi_info
            }
        )
    except Exception as e:
        logger.error(f"Error getting WiFi status: {e}")
        return templates.TemplateResponse(
            "partials/wifi_status.html",
            {
                "request": request,
                "wifi_info": {}
            }
        )

@ui_config_router.get("/api/wifi/networks", response_class=HTMLResponse)
async def wifi_networks(request: Request):
    """Get available WiFi networks"""
    try:
        networks = wifi_manager.scan_networks()
        return templates.TemplateResponse(
            "partials/wifi_networks.html",
            {
                "request": request,
                "networks": networks
            }
        )
    except Exception as e:
        logger.error(f"Error scanning networks: {e}")
        return templates.TemplateResponse(
            "partials/wifi_networks.html",
            {
                "request": request,
                "networks": []
            }
        )

@ui_config_router.post("/api/wifi/connect")
async def connect_wifi(request: Request, ssid: str = Form(...), password: str = Form(...)):
    """Connect to WiFi network"""
    success = wifi_manager.connect_to_network(ssid, password)
    if success:
        return JSONResponse(content={"status": "success", "message": "Connected successfully"})
    return JSONResponse(
        status_code=400,
        content={"status": "error", "message": "Failed to connect to network"}
    )

@ui_config_router.get("/api/wifi/networks")
async def get_wifi_networks():
    networks = wifi_manager.scan_networks()
    return {"networks": networks}

@ui_config_router.post("/api/wifi/connect")
async def connect_wifi(ssid: str, password: str):
    success = wifi_manager.connect_to_network(ssid, password)
    if success:
        return {"status": "connected"}
    raise HTTPException(status_code=500, detail="Could not connect to network")

@ui_config_router.get("/api/logs", response_class=HTMLResponse)
async def get_logs(request: Request):
    """Get the latest logs from iot_gateway.log"""
    try:
        log_file = "logs/iot_gateway.log"
        
        if not os.path.exists(log_file):
            return templates.TemplateResponse(
                "logs.html",
                {
                    "request": request,
                    "logs": ["Log file not found"],
                    "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            )

        # Read last 100 lines of the log file
        with open(log_file, 'r') as f:
            from collections import deque
            last_lines = deque(f, 100)
            logs = list(last_lines)

        return templates.TemplateResponse(
            "logs.html",
            {
                "request": request,
                "logs": logs,
                "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        )
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return templates.TemplateResponse(
            "logs.html",
            {
                "request": request,
                "logs": [f"Error reading logs: {str(e)}"],
                "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        )
    
@ui_config_router.get("/api/download-logs")
async def download_logs():
    """Zip all logs in the logs folder and send them as a download"""
    try:
        log_extenstion_regex = r"\.log(\.\d+)?$"
        pattern = re.compile(log_extenstion_regex)
        # Create a BytesIO object to store the zip file
        zip_buffer = io.BytesIO()
        
        # Create a ZipFile object
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Walk through the logs directory
            for root, dirs, files in os.walk("logs"):
                for file in files:
                    if pattern.search(file): # Only include .log files
                        file_path = os.path.join(root, file)
                        # Add file to zip with its relative path
                        zip_file.write(file_path, os.path.basename(file_path))
        
        # Seek to the beginning of the BytesIO buffer
        zip_buffer.seek(0)
        
        # Return the zip file as a downloadable response
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            }
        )
    except Exception as e:
        logger.error(f"Error creating log zip file: {e}")
        raise HTTPException(status_code=500, detail=str(e))