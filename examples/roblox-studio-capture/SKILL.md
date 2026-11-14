---
name: studio-capture
description: Take Roblox Studio screenshots to files and check them by numbers, instead of the Studio MCP screen_capture tool (which returns the image into the chat). Use whenever a task needs frames for owner approval, art previews, or any picture of the game. By default nobody opens the frames; design roles may open them only if the project's image policy allows it.
---

# Studio captures to file (example of an environment-specific skill)

Frames go to files, never into the chat. This needs a small capture script in the project (here `scripts/capture-studio.sh`) that finds a window by title, brings it to the front, grabs it, and prints stats per frame.

Who may open a frame: only if the project's image policy in `CLAUDE.md` opts design roles in, `designer` and `visual-reviewer` may open their own capture files. Everyone else reports numbers only. MCP `screen_capture` is banned for everybody.

## Before the first capture

- **Own window per task.** Open a dedicated Studio window whose title contains the task id, pass that title to every capture so another window is never grabbed, and close it at the end. Respect the project's limit on concurrent Studio windows.
- The window must be visible and the display awake (a locked display gives blank frames). The machine should be idle during capture runs: the window is raised for about 2 s per grab.
- Every frame's output must show the window was in front (`fg=true`). If not, retake once, then report it. Never retry in a loop and never touch other applications' windows.
- **Device simulator frames:** the focus trick (an Alt key press) can flip the simulator's preferred input from touch to keyboard/mouse, and UI that scales on input type then shows desktop scale. For simulator frames use a key-free focus path, and read the preferred input and UI scale back afterwards to put them in the report.

## Before every Play

Mute first, so nothing plays on the owner's speakers: set a mute attribute in the Edit data model that the game's sound controller honours in Studio, and after Play starts read back that the master volume is 0. If it is not, stop Play at once and report.

## Taking a frame

1. Stage the state with `execute_luau` (test hooks, clear daylight, UI hidden unless it is the subject). Real build only; merge pending art first and rebuild your window.
2. Hold the camera with a per-frame render-step binding (setting it once is not enough; tooling can reset the camera type when a call ends). Wait about 3 s so textures and meshes load; unbind afterwards.
3. Read the camera position and the staged state back as numbers for the report.
4. Find the viewport box once (a full-screen magenta overlay, then remove it), capture into `docs/reports/screens/<task-id>/<NN-name>.jpg` (git-ignored), and check the size against the viewport times the display scale.

## Checking without looking

Per frame the script prints size, byte count, number of colours on a thumbnail, top-colour share, focus flag and an md5.

- Very few colours or a top colour near 100%: suspect a blank frame. Retake once, then report.
- Two frames from different cameras with the same md5: the window is not repainting. Stop and report.
- Brightness of a region (e.g. comparing quality levels) can be measured as mean luma without saving anything.

These numbers catch blank and frozen frames and measure brightness. They say nothing about whether the framing or the art is right; say that in the report.

## Report

List each file with what was staged and the camera position. Mark frames "unviewed, waits for owner" unless your role is opted in and you opened them. Add new sets to the approval list in the status doc.
