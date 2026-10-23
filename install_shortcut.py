"""Install QuickPane launchers; assign the global shortcuts in KDE settings."""

from pathlib import Path

root = Path(__file__).resolve().parent
target = Path.home() / ".local/share/applications/quickpane.desktop"
target.parent.mkdir(parents=True, exist_ok=True)

entries = {
    target: ("QuickPane", "Floating ChatGPT panel for text and screenshots", ""),
    target.with_name("quickpane-toggle.desktop"): (
        "QuickPane - Toggle window", "Show or hide QuickPane", " --toggle"),
    target.with_name("quickpane-capture.desktop"): (
        "QuickPane - Capture screenshot", "Capture an area and attach it to QuickPane", " --capture"),
}

for path, (name, comment, args) in entries.items():
    path.write_text(f"""[Desktop Entry]
Type=Application
Name={name}
Comment={comment}
Exec={root / 'run.sh'}{args}
Icon={root / 'assets/quickpane-icon.png'}
Terminal=false
Categories=Utility;
StartupNotify=true
""", encoding="utf-8")
    print(f"Installed: {path}")

print("In KDE System Settings → Shortcuts, assign Ctrl+Alt+Space to toggle QuickPane and Ctrl+Alt+P to capture a screenshot.")
