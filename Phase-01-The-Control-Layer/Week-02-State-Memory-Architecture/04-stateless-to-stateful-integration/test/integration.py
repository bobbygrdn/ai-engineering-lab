import subprocess
import sys

def run_cli(inputs):
    proc = subprocess.Popen(
        [sys.executable, "src/main.py", "--test-mode"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    # Send the sequence of inputs, separated by newlines
    out, err = proc.communicate('\n'.join(inputs) + '\n')
    print("STDOUT:\n", out)
    print("STDERR:\n", err)

# Step 1: Register and first message
run_cli([
    "register",
    "robert1",         # Use a unique username
    "testpass",
    "robert1@example.com",
    "login",
    "robert1",
    "testpass",
    "Hi, I'm Robert. I'm having trouble with my password.",
    "exit",
    "", "", ""  # Extra lines for safety
])

# Step 2: Login and check ticket
run_cli([
    "login",
    "robert1",
    "testpass",
    "Check the status of my ticket.",
    "exit"
])

# Step 3: Login and update email
run_cli([
    "login",
    "robert1",
    "testpass",
    "I also need to update my email.",
    "exit"
])