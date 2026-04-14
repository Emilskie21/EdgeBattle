**Edge - Shadow Boxing Game**


**OVERVIEW**

Edge is a boxing game where you dodge punches using your head. The game watches you through your webcam and reads which way you tilt your head. An arrow appears on screen pointing in one direction. Your job is to tilt your head the opposite way before the arrow disappears. If you move in the same direction as the arrow, or do nothing, you take a hit. You have 3 lives. Every arrow you dodge earns you points. The arrows come faster as your score goes up, so the challenge grows the longer you survive.

There is a leaderboard that keeps track of all scores from the current session. When a round ends, you type in your name and see where you placed. You can play again immediately or hand off to another person by running a new calibration for them.


**TECHNICALITIES**

**Language and Libraries**

The game is written in Python. It uses Pygame to draw the screen, play sounds, and run the game loop at 60 frames per second. It uses MediaPipe and OpenCV to read from the webcam and figure out which way your head is pointing.

**Head Tracking**

When the game starts, it opens the webcam at 320 by 240 pixels and targets 60 frames per second. The camera buffer is set to hold only 1 frame at a time so the reading is as fresh as possible. A background thread runs continuously, grabbing frames and feeding them into a MediaPipe face landmark model called FaceLandmarker. That model finds 6 specific points on your face (eye corners, nose tip, mouth corners, and chin). OpenCV then takes those points and solves a math problem called PnP to figure out your head rotation as pitch (up/down tilt) and yaw (left/right turn) in degrees.

During gameplay the smoothing window is 1 frame, meaning the raw angle from each frame is used directly with no averaging delay. A direction is only registered when it crosses 10 degrees away from your calibrated neutral. Once a direction fires, there is a 2-frame cooldown before the same direction can fire again.

**Calibration**

Before the game, a calibration step records your neutral head position. You center your face in an oval on screen, hold still looking forward, then briefly turn left, right, up, and down to confirm the system can read each direction. The result is saved to a file so it persists between sessions. If no calibration file exists, the game seeds one automatically from the first detected face.

**Scoring and Difficulty**

Each arrow you dodge earns 20 points. The window of time each arrow stays on screen starts at 1000 milliseconds and shrinks by 0.4 milliseconds for every point you earn, down to a floor of 450 milliseconds.

**Data Storage**

The leaderboard is stored in a SQLite database file. Your personal high score and display settings are saved in a JSON file. Both files sit in the data folder of the project.


**HOW TO USE**

**Requirements**

You need Python installed along with the following packages: pygame, mediapipe, opencv-python (cv2), and numpy. You also need a working webcam.

If you are setting up for the first time, create a virtual environment and install dependencies:

  python -m venv .venv

On Windows:
  .venv\Scripts\Activate.ps1

On Mac or Linux:
  source .venv/bin/activate

Then:
  pip install -r requirements.txt

**Running the Game**

To launch the game including calibration, run:

  python main.py

The program will open a calibration window first. Follow the instructions on screen to set your neutral head position. Once calibration is done, the game window opens automatically.

If you want to skip calibration and go straight to the game (for example, if you already calibrated recently), set this environment variable before running:

  SHADOW_BOXING_SKIP_CAL=1 python main.py

To run calibration on its own without starting the game:

  python run_calibration.py

**Controls**

  C         Run calibration from the menu
  Enter     Start the game after calibration is done
  O         Open the options screen during gameplay
  D         Toggle the debug overlay (shows FPS and detected direction)
  Escape    Return to the menu or quit

After a round ends, type your name and press Enter to save your score. Then press 1 to play again with the same calibration, or press 2 to recalibrate for a different player.


**LATENCY PIPELINE**

This table shows each step the system goes through from the moment you move your head to the moment the game registers it. Times are based on the settings in the code at 60 frames per second.


| **Step** | **What Happens** | **Time per Frame** |
| -------- | -------- | -------- |
| Camera capture | Webcam grabs a frame at 320x240 | ~16.7 ms |
| Buffer flush | Buffer size is 1, so old frames are dropped | 0 ms extra |
| MediaPipe detection | Face landmarks found in background thread | runs in parallel |
| PnP solve Background thread | Head angles computed from 6 landmarks | runs in parallel |




