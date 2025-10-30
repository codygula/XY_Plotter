import json

try:
    with open('settings.json', 'r') as file:
        data = json.load(file)
        print(data)
except FileNotFoundError:
    print("Error: The file 'data.json' was not found.")
except json.JSONDecodeError:
    print("Error: Failed to decode JSON from the file.")


LimitA = 0
LimitPaperAdvance = 0


def alarm():
    pass

def backlight(status):
    pass

def paperFeed():
    pass

def paperTakeUp():
    if data["PaperTakeUpMode"] == False:
        print("FALSE!!!")
    # pass

def inkPump():
    pass




running = True
while running:
    # do stuff.
    # listern for things and stuff with apis or magic of something.
    # when a thing or stuff happens, run:
        # Text_to_svg
        # Simulation.py
    # continue waiting
    # print("while loop running")
    pass