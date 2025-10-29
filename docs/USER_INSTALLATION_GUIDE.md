# 🚀 AssistedDiscovery Installation Guide For Windows and MacOS

Welcome to AssistedDiscovery! This guide will walk you through the simple steps to get the application running on your Mac.

### What You'll Need

*   The AssistedDiscovery zip file provided to you.
*   A computer running **macOS** or **Windows**
*   **Python 3.12**: Please ensure you have Python version 3.12 installed. You can download it from [python.org](https://www.python.org/downloads/release/python-3120/).


---

## ⚙️ Step 1: Installation (One-Time Setup)

This first step installs the application and its dependencies. You only need to do this once.

### For MacOS:
1.  **Unzip the File**
    *   Find the `AssistedDiscovery-Mac.zip` file.
    *   To unzip it, you can usually **double-click** the file. If that doesn't work, **right-click** on it and select **"Extract All..."**.
    *   This will create a new folder named `AssistedDiscovery-Mac`.

2.  **Run the Setup Script**
    *   Open the new `AssistedDiscovery-Mac` folder.
    *   Find the `setup.sh` file. You will need to run this from the **Terminal** app:
        *   Open the **Terminal** app.
        *   Enter `./setup.sh` and press **Enter**.
        *   The installation will begin.

### For Windows:

1.  **Unzip the File**
    *   Find the `AssistedDiscovery-Windows.zip` file.
    *   To unzip it, you can usually **double-click** the file. If that doesn't work, **right-click** on it and select **"Extract All..."**.
    *   This will create a new folder named `AssistedDiscovery-Windows`.

2.  **Run the Setup Script**
    *   Open the new `AssistedDiscovery-Windows` folder.
    *   Find the `setup.bat` file. You will need to run this from the **Command Prompt** app:
        *   Open the **Command Prompt** app.
        *   Enter `setup.bat` and press **Enter**.
        *   The installation will begin.

> **Note:** The setup process can take a few minutes as it downloads and installs the necessary components. Please be patient and wait for it to complete.

---

## Step 2: Starting the Application

Once the setup is complete, you can start the application anytime by following these steps.

### For MacOS:
1.  **Run the Start Script**
    *   In the same terminal, run `./start_app.sh`.
    *   The application will start and open your web browser to the AssistedDiscovery application.

2.  **Access the Application**
    *   If it doesn't open automatically, you can manually open your browser and go to: **http://localhost:8501**

### For Windows:
1.  **Run the Start Script**
    *   In the same terminal, run `./start_app.bat`.
    *   The application will start and open your web browser to the AssistedDiscovery application.

2.  **Access the Application**
    *   If it doesn't open automatically, you can manually open your browser and go to: **http://localhost:8501**

> **Important:** Keep the terminal window open while you are using the application. Closing it will shut down the application.

### Troubleshooting

*   **Application doesn't open in the browser?**
    *   Make sure you are connected to the internet and that no other applications are using port 8501. Manually navigate to `http://localhost:8501` in your browser.
*   **"Connection Error" in the UI?**
    *   This usually means your LLM credentials in the **Config** page are incorrect. Double-check them and test the connection again.
    *   Ensure you have restarted the application after saving your credentials.