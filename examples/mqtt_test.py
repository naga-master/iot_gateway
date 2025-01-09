import paho.mqtt.client as mqtt
import json

# Replace with your MQTT broker address
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883

# Topics to subscribe and publish
SUBSCRIBE_TOPIC = "temperature/sensor1"
SUBSCRIBE_TOPIC_1 = "temperature/sensor2"
ACK_TOPIC = "temperature/ack"

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {str(rc)}")
    # Subscribe to the temperature topic
    client.subscribe(SUBSCRIBE_TOPIC)
    client.subscribe(SUBSCRIBE_TOPIC_1)

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        print(msg.topic, data)
        sensor_id = data.get("device_id")
        reading_id = data.get("reading_id")

        if sensor_id and reading_id:
            ack_message = {"device_id": sensor_id, "reading_id": reading_id}
            client.publish(ACK_TOPIC, json.dumps(ack_message))
            print(f"Published ACK for device_id: {sensor_id}, reading_id: {reading_id}")

    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON message: {msg.payload}")

# Create an MQTT client instance
client = mqtt.Client()

# Set the callbacks
client.on_connect = on_connect
client.on_message = on_message

# Connect to the MQTT broker
client.connect(MQTT_BROKER, MQTT_PORT, 60)

# Start the MQTT loop
client.loop_forever()