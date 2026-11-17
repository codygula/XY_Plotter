Restoration of a 1950s Telautograph device. 
![1000006357](https://github.com/user-attachments/assets/9c00d7aa-2456-4686-b177-ee048bb0ccda)


## Files

- `main.py` – controller. Runs setup once at power-on, then waits for text commands over WiFi or serial and plots them.
- `Text_to_svg.py` – turns a string of text into a single-stroke SVG.
- `Plotter.py` – drives the 5-bar linkage (two DACs via the Arduino + pen lift) to draw an SVG. No GUI.
- `debugScripts/Simulation.py` – pygame GUI version of the plotter, for re-tuning the calibration constants (`minA`, `maxA`, `minB`, `maxB`). Copy tuned values into `Plotter.py`.

## Sending text to the plotter

Over WiFi (TCP port 5000, one line of text per connection), from any computer on the same network:

```bash
echo "HELLO WORLD" | nc <pi-address> 5000
```

Over serial: send a line of text ending in a newline to `COMMAND_SERIAL_PORT` in `main.py` (default `/dev/serial0`, the Pi's GPIO UART; enable it with `sudo raspi-config` → Interface Options → Serial Port: login shell **No**, hardware **Yes**).

Use `\n` in the text for a line break. The plotter replies `QUEUED`, `PLOTTING`, then `DONE` or `ERROR: ...`.

## Run main.py automatically at boot

On the Pi (adjust the user and paths in `xy_plotter.service` first if they differ from `gula` and `/home/gula/Telautograph/XY_Plotter`):

```bash
sudo cp xy_plotter.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now xy_plotter.service
```

Check that it's running and watch its output:

```bash
systemctl status xy_plotter.service
journalctl -u xy_plotter.service -f
```

Stop it (e.g. to run `debugScripts/Simulation.py`, which needs the same Arduino serial port):

```bash
sudo systemctl stop xy_plotter.service
```
