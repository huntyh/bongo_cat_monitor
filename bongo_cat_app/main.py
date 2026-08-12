#!/usr/bin/env python3
"""
Bongo Cat Application - Main Entry Point
Fixed threading model - Engine ALWAYS runs on main thread for proper keyboard timing
"""

import sys
import os
# Force UTF-8 encoding for Windows console to support emojis
os.environ['PYTHONUTF8'] = '1'
if sys.stdout:
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr:
    sys.stderr.reconfigure(encoding='utf-8')

import signal
import argparse
import threading
import time
from pynput import keyboard
from config import ConfigManager
from engine import BongoCatEngine
from tray import BongoCatSystemTray

class BongoCatApplication:
    """Main Bongo Cat application with FIXED thread-safe GUI"""
    
    def __init__(self, start_minimized=False):
        """Initialize the application"""
        self.start_minimized = start_minimized
        self.config = None
        self.engine = None
        self.tray = None
        self.tk_root = None
        self.running = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully"""
        print('\n🛑 Shutting down gracefully...')
        self.shutdown()
    
    def initialize_components(self):
        """Initialize all application components"""
        try:
            # Initialize configuration manager
            print("📂 Loading configuration...")
            self.config = ConfigManager()
            
            # Initialize engine with configuration
            print("🔧 Initializing Bongo Cat Engine...")
            self.engine = BongoCatEngine(config_manager=self.config)
            
            # Initialize system tray (but don't start it yet)
            print("📱 Setting up system tray...")
            self.tray = BongoCatSystemTray(
                config_manager=self.config,
                engine=self.engine,
                on_exit_callback=self.shutdown
            )
            
            # Connect engine to tray for status updates
            self.engine.set_tray_reference(self.tray)
            
            # Connect tray to config for settings refresh
            self.config.add_change_callback(self.tray.on_config_change)
            
            return True
            
        except Exception as e:
            print(f"❌ Initialization error: {e}")
            return False
    
    def run(self):
        """Run the main application with FIXED threading model"""
        print("🐱 Bongo Cat Application v2.1 - FIXED THREADING")
        print("=" * 60)
        
        # Initialize components
        if not self.initialize_components():
            return 1
        
        self.running = True
        
        try:
            # CRITICAL FIX: Use pystray run_detached() method for proper GUI/tray coexistence
            print("📱 Starting system tray with run_detached()...")
            self.tray.start_detached()
            
            # Update initial connection status
            print("🔄 Checking initial connection status...")
            
            if self.start_minimized:
                print("🔕 Running in background mode...")
                print("📱 Look for the cat icon in your system tray")
                print("🖱️ Right-click the tray icon for options")
                print("⌨️ Keyboard monitoring active on main thread")
            else:
                print("🖥️ Running in normal mode...")
                print("📝 Start typing to see your cat react!")
                print("🔄 System tray available in background")
                print("🛑 Press Ctrl+C to stop")
            
            print("✅ System tray started with run_detached()")
            print("💡 Settings window available from tray menu")
            print("🎯 Starting animation engine on MAIN THREAD for optimal responsiveness...")
            
            # CRITICAL FIX: Engine ALWAYS runs on main thread (like original script)
            # This ensures proper keyboard listener timing regardless of start mode
            monitoring_started = self.engine.start_monitoring()
            
            if not monitoring_started:
                # Serial connection failed - keep tray alive and retry in background
                print("\n⚠️ ESP32 not available - keeping tray alive for background retry...")
                print("🔄 Will retry connection every 10 seconds")
                print("🖱️ Right-click tray icon for manual reconnect options")
                self._start_background_retry()
            else:
                # Normal flow - start_monitoring() is blocking (keyboard listener.join())
                # When it returns, we fall through to shutdown
                pass
                
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")
        except Exception as e:
            print(f"❌ Runtime error: {e}")
            import traceback
            traceback.print_exc()
            return 1
        finally:
            self.shutdown()
        
        return 0

    def _start_background_retry(self):
        """Start background retry loop when ESP32 is unavailable.
        Keeps the tray alive and periodically attempts to reconnect."""
        retry_interval = 10  # seconds
        self.engine._retry_stop_event = threading.Event()
        self.engine._retry_running = True
        
        # Update tray to show retry in progress
        if self.tray:
            self.tray.update_connection_status("connecting")
        
        def retry_loop():
            attempt = 0
            while not self.engine._retry_stop_event.is_set():
                attempt += 1
                # Show "connecting" status while waiting
                if self.tray:
                    self.tray.update_connection_status("connecting")
                print(f"\n🔄 Retry attempt {attempt} in {retry_interval}s...")
                if self.engine._retry_stop_event.wait(timeout=retry_interval):
                    break  # Stop signal received
                
                # Force port re-scan each retry cycle so it doesn't stick to unplugged COM ports
                self.engine.port = 'AUTO'
                print("🔌 Attempting to reconnect to ESP32...")
                if self.engine.connect_serial():
                    print("✅ Connected! Starting monitoring...")
                    self.engine._retry_running = False
                    # Update tray status
                    if self.tray:
                        self.tray.update_connection_status("connected")
                    # Start system monitor
                    self.engine.start_system_monitor()
                    # Start animation loop
                    update_thread = threading.Thread(target=self.engine.update_animation_loop, daemon=True)
                    update_thread.start()
                    # Start keyboard listener (blocking)
                    try:
                        with keyboard.Listener(on_press=self.engine.on_key_press) as listener:
                            listener.join()
                    except KeyboardInterrupt:
                        pass
                    break
                else:
                    print("❌ Retry failed - port still unavailable")
                    # Keep showing connecting status for next retry
        
        retry_thread = threading.Thread(target=retry_loop, daemon=True)
        retry_thread.start()
        
        # Keep main thread alive for the tray to function
        # Use a blocking wait that can be interrupted
        while self.running:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Interrupted by user")
                break
    
    def shutdown(self):
        """Shutdown the application gracefully"""
        if not self.running:
            return  # Prevent double shutdown
        
        print("🛑 Shutting down components...")
        
        self.running = False
        
        # Stop background retry thread if running
        if self.engine and hasattr(self.engine, '_retry_stop_event'):
            self.engine._retry_stop_event.set()
        
        # Stop engine first
        if self.engine:
            self.engine.stop_monitoring()
        
        # Stop system tray
        if self.tray:
            self.tray.stop()
        
        # Clean up tkinter root if it exists
        if hasattr(self, 'tk_root') and self.tk_root:
            try:
                self.tk_root.destroy()
            except:
                pass
        
        print("👋 Goodbye!")
        sys.exit(0)

def main():
    """Main application entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Bongo Cat Typing Monitor")
    parser.add_argument("--minimized", action="store_true", 
                       help="Start minimized to system tray")
    parser.add_argument("--startup", action="store_true",
                       help="Started automatically with Windows")
    
    args = parser.parse_args()
    
    # Determine start mode
    start_minimized = args.minimized or args.startup
    
    # Create and run application
    app = BongoCatApplication(start_minimized=start_minimized)
    return app.run()

if __name__ == "__main__":
    sys.exit(main())
