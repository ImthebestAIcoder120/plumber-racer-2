# Plumber Racer 2: install tutorial

Plumber Racer 2 runs Mario Kart World on an iPhone or a Mac. This guide takes you from your own copy of the game to playing it on an iPhone: you build an app on a Mac, install it in LiveContainer, and copy the game files across. To play on the Mac itself, which is simpler, follow Steps 1 to 3 and then [Playing on a Mac](#playing-on-a-mac).

**This repository has no game files, keys or ready-made apps.** You need your own dump of the game. The app and the `RomFS.img` file you make here contain your game, so keep them to yourself.

**What to expect:** a whole Grand Prix cup has finished on an iPhone 18 Pro, but 60 fps is not stable yet. A race holds 60 fps for about a minute, then can fall to about 40. Other iPhones and the other modes are untested, and online play, local wireless and GameChat are not available. Details are in the [game's note](dm/games/0400C3F00006E000/README.md#status).

## What you need

| | |
|---|---|
| **The game** | Your own dump of Mario Kart World **version 1.0.0**: the base game with no update and no DLC |
| **A Mac** | macOS 26.6 or later, Apple silicon, Xcode 27.2, and about 50 GB free (22 GB for the dump, 27 GB for the build) |
| **An iPhone** | Tested only on an iPhone 18 Pro, with about 28 GB free |
| **LiveContainer** | Installed on the iPhone. See [LiveContainer's own instructions](https://github.com/LiveContainer/LiveContainer) |

## Step 1: Check your game version

Only this exact build works. The code patches are made for these modules, so an update or another version will not run.

| | |
|---|---|
| Title ID | `0400C3F00006E000` |
| Version | 1.0.0 |
| `main` build ID | `9e244438c3d8ef1c703a6a85ef99c4f0` |
| `subsdk0` build ID | `d39a7a3d44530bb61b35690e5b0383d5` |
| `sdk` build ID | `90ebba182862b9ecdc21fcb87b999012` |

## Step 2: Put the game files in a folder

Make a folder on the Mac and lay out your dump exactly like this. The folder's name and location are up to you, but the `base`, `exefs` and `romfs` names are not:

```
Mario Kart World/
  base/
    exefs/
      main
      main.npdm
      rtld
      sdk
      subsdk0
    romfs/
      (all of the game's files and folders)
```

Check your dump against the table in Step 1. In Terminal, this prints the build ID of `main`, which should match exactly:

```bash
xxd -s 0x40 -l 16 -p "$HOME/Games/Mario Kart World/base/exefs/main"
```

Change the path if you put the folder somewhere else. To check the other two modules, replace `main` at the end of the path with `subsdk0` and `sdk`.

## Step 3: Set up the Mac

You only do this once.

1. Install [Xcode 27.2](https://developer.apple.com/download/all/?q=Xcode%2027.2) and open it once. Add its iOS platform in **Xcode → Settings → Components**.
2. Install [Homebrew](https://brew.sh) and Python 3.12 or newer (an arm64 Python, not an Intel Homebrew's).
3. In Terminal, select Xcode and get the Metal tools:

   ```bash
   sudo xcode-select -s /Applications/Xcode.app
   ```

   ```bash
   xcodebuild -downloadComponent MetalToolchain
   ```

4. Download this repository and go into it:

   ```bash
   git clone https://github.com/cheemu21/plumber-racer-2.git
   ```

   ```bash
   cd plumber-racer-2
   ```

5. Install the build tools:

   ```bash
   brew install xcodegen zstd glslang
   ```

   ```bash
   brew install --cask dotnet-sdk
   ```

6. Make a Python environment for the build and install its packages:

   ```bash
   python3 -m venv .venv
   ```

   ```bash
   source .venv/bin/activate
   ```

   ```bash
   python3 -m pip install lz4 "capstone>=5,<6" fonttools nsz zbic "backports.zstd; python_version < '3.14'"
   ```

If you open a new Terminal window later, go back into the repository folder and run `source .venv/bin/activate` again before building.

## Step 4: Build the app

From the repository folder, run this with the path to your game folder:

```bash
python3 scripts/build_ipa_from_nsp.py "$HOME/Games/Mario Kart World" --platform ios --romfs separate
```

No `prod.keys` is needed for a dump. The first build compiles 11,561 shaders, which takes 20 to 30 minutes on an M5, and your Mac may be slow during that time. Later builds reuse them and take about a minute.

When it finishes, your game folder holds the two files you need:

| File | Size | What it is |
|---|---|---|
| `MarioKartWorld.ipa` | about 690 MB | The app |
| `0400C3F00006E000_build/extract/v0/RomFS.img` | 21.7 GB | The game files |

The script's last lines suggest a `scripts/push_romfs.sh` command. Skip it: that's for apps installed directly on the phone, and with LiveContainer you copy the file by hand in Step 6.

A blank home-screen icon is normal too, because a dump has no icon data.

## Step 5: Install the app

1. Send `MarioKartWorld.ipa` to your iPhone, for example with AirDrop, and save it to the Files app.
2. Open LiveContainer and install the IPA in it. If you sideload LiveContainer with a tool that offers **Increased Memory Limit**, turn that on: the game needs it.

Don't start the game yet.

## Step 6: Put the game files on the iPhone

The game files go in the app's own **Documents** folder.

**1. Get `RomFS.img` onto the iPhone.** Any of these can work:

- **A USB-C drive** formatted as APFS or exFAT. FAT32 can't hold a file this big.
- **AirDrop**, choosing to save it to the Files app.
- **Finder**, with the iPhone connected by cable: select the iPhone, open the **Files** tab, and drag the file onto LiveContainer.

**2. Find the game's folder.** In the Files app, open:

**On My iPhone → LiveContainer → Data → Application → (the game's folder) → Documents**

The folders in `Application` have long, random-looking names. LiveContainer's settings for the app show which one belongs to the game.

**3. Put `RomFS.img` in that Documents folder.** If the file is already on the iPhone, use **Move** rather than **Copy**: a copy needs another 21.7 GB free.

**4. Wait for it to finish.** Don't launch the game while the file is still arriving. The app ignores a file that was cut off partway.

The finished folder looks like this:

```
Documents/
  RomFS.img
```

The upper and lower case in the name doesn't matter.

**5. Keep at least 5 GB free on top of that.** While it runs, the game keeps its memory in a temporary file. With under 4 GB free at launch, it falls back to normal memory and runs out during a race.

## Step 7: Play

Start the game from LiveContainer. A settings screen comes first: tap **Play**. The first launch then builds its pipelines for about 30 seconds behind a progress screen.

A frame-rate counter is on by default. To hide it, put a text file named `env.txt` in the same Documents folder, containing the line `DM_SHOW_FPS=0`.

The touch controls are made for racing:

| Control | Touch button |
|---|---|
| Steer | Floating stick |
| Accelerate, brake | Gas and brake pedals |
| Drift, charge jump, tricks | A + R (drift button) |
| Use an item | A + L (item button) |
| Look back | X |
| Rewind | D-pad down (REWIND) |
| Map | Y (MAP) |
| Menu buttons | + and − |
| Quick spin | Gas and brake together |

Sliding your thumb between gas, drift and item keeps A held. The camera (right stick) has no touch control.

Saves are in the app's Documents folder.

## Playing on a Mac

The game also runs on a Mac with Apple silicon. There is nothing to sideload or copy, because the Mac app carries the game files inside it.

1. Follow Steps 1 to 3 above.
2. Build the Mac app, from the repository folder, with the path to your game folder:

   ```bash
   python3 scripts/build_ipa_from_nsp.py "$HOME/Games/Mario Kart World" --platform mac-app
   ```

3. Open `Mario Kart World.app` from your game folder. It is about 23 GB and works from any folder once built. The first time you open it, macOS can sit silently for over a minute while it scans the app, so give it time.
4. A settings window appears before the game starts.

**What to expect:** tested on an M5 Mac with 16 GB of memory, a race runs at about 50 fps. The game is heavy on memory, and a Mac that runs short starts swapping, slows right down and can become hard to use. Close other apps before you play, and quit the game if the Mac starts to struggle.

The touch controls are on the iPhone only. On the Mac you need a controller, and playing this game with one has not been tested yet.

The log is at `~/Library/Logs/nxnative/0400C3F00006E000.log`.

## If something goes wrong

The app writes a log to `log.txt` in the same Documents folder, and keeps the previous run's as `log.prev.txt`. Check it first.

| What you see | What to do |
|---|---|
| The game doesn't start | Check that `RomFS.img` is directly in the game's Documents folder and has finished copying (21.7 GB), and that it came from the same dump as the app |
| `is not the image this build needs` in the log | The file doesn't match this app. Copy over the `RomFS.img` from the same build as your IPA |
| The game closes during a race | Free up storage (Step 6), then find `footprint X MiB (limit in Y MiB)` in the log. X + Y is the app's memory limit, 8,192 on the iPhone 18 Pro. A much lower total means the increased memory limit isn't on |
| The build stops at the shaders | Check that Xcode 27.2 is selected (Step 3): the shaders are built with its Metal compiler |
| Wrong version or a crash at boot | Compare your build IDs with Step 1 |
| The frame rate drops after about a minute | This is the known open problem. It isn't your setup |

## Updating

1. Get the latest code with `git pull`.
2. Run the build command in Step 4 again.
3. Install the new `MarioKartWorld.ipa` in LiveContainer over the old one.

The game's data stays, so you don't need to copy `RomFS.img` again unless your dump changed. Removing the app's data deletes `RomFS.img` and your saves.

## More

- [The game's note](dm/games/0400C3F00006E000/README.md): how it works, its status and what is still open
- [Main README](README.md): the nxnative project and its other games
