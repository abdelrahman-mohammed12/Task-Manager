# Task Manager (Kivy / Android)

Daily tasks: one-time and repeat-every-day tasks, per-day completion history,
colour-coded list, progress bar. Tasks are stored in the app's private
folder (`App.user_data_dir`) - no storage permission needed.

## Build the APK with GitHub Actions
1. Create a GitHub repository and push this folder to the `main` branch.
2. Open the **Actions** tab -> **Build APK** (it starts on every push; or press *Run workflow*).
3. When it finishes (first run ~25-40 min, later runs use the cache), download
   the **TaskManager-apk** artifact -> `TaskManager.apk`.
4. Copy it to the phone and install (allow "install unknown apps").

## Run on desktop
    pip install -r requirements.txt
    python main.py

## Tests (task logic)
    python -m unittest discover -s tests -v
