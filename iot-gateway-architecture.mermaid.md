```mermaid
graph TB
    subgraph "Device Layer"
        BLE["Bluetooth Adapter"]
        WIFI["WiFi Adapter"]
        MQTT["MQTT Adapter"]
        I2C["I2C Adapter"]
        SPI["SPI Adapter"]
        UART["UART Adapter"]
        GPIO["GPIO Adapter"]
        REST["REST API Adapter"]
    end

    subgraph "Core Layer"
        EM["Event Manager"]
        DM["Device Manager"]
        PM["Protocol Manager"]
        CM["Configuration Manager"]
    end

    subgraph "Processing Layer"
        DP["Data Processor"]
        BP["Business Processor"]
        TR["Transformation Rules"]
    end

    subgraph "Storage Layer"
        LC["Local Cache"]
        PS["Persistent Storage"]
        SM["Sync Manager"]
    end

    %% Connections
    BLE & WIFI & MQTT & I2C & SPI & UART & GPIO & REST --> EM
    EM --> DM & PM
    DM & PM --> DP
    DP --> BP
    BP --> TR
    TR --> LC
    LC --> PS
    PS --> SM
    CM --> EM & DM & PM & DP & BP & TR & LC & PS & SM
    ```
