import subprocess
import sys
import os
import time

def run_command(command, cwd=None, capture_output=True):
    """
    Runs a shell command and captures its output.
    Returns (True, stdout) on success, (False, stderr/error_message) on failure.
    """
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,  # Raises CalledProcessError if command returns non-zero exit status
            text=True,   # Decode stdout/stderr as text
            capture_output=capture_output # Capture stdout and stderr
        )
        if capture_output:
            return True, result.stdout.strip()
        return True, ""
    except subprocess.CalledProcessError as e:
        error_msg = f"ERROR: Command '{' '.join(command)}' failed with exit code {e.returncode}\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"
        print(error_msg, file=sys.stderr)
        return False, error_msg
    except FileNotFoundError:
        error_msg = f"ERROR: Git command not found. Please ensure Git is installed and in your PATH."
        print(error_msg, file=sys.stderr)
        return False, error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred: {e}"
        print(error_msg, file=sys.stderr)
        return False, error_msg

def auto_git_push():
    """
    Monitors for Git changes every 10 seconds.
    If changes are detected, prompts the user for a commit message and pushes.
    """
    project_root = os.path.dirname(os.path.abspath(__file__))
    print(f"Monitoring changes in: {project_root}")
    print("Press Ctrl+C to stop the monitoring.")

    while True:
        try:
            # Check for changes
            success, status_output = run_command(["git", "status", "--porcelain"], cwd=project_root)
            
            if not success:
                print(f"Error checking git status. Retrying in 10 seconds...")
                time.sleep(10)
                continue

            if status_output: # If status_output is not empty, there are changes
                print("\n--- Changes detected! ---")
                print(status_output) # Show what changed
                
                commit_message = input("Enter your commit message (or press Enter to skip this cycle): ").strip()

                if commit_message:
                    # Step 1: Add all changes
                    print("\n--- Running git add . ---")
                    add_success, _ = run_command(["git", "add", "."], cwd=project_root)
                    if not add_success:
                        print("Failed to add files. Skipping push for this cycle.", file=sys.stderr)
                        time.sleep(10)
                        continue

                    # Step 2: Commit changes
                    print("\n--- Running git commit ---")
                    commit_success, _ = run_command(["git", "commit", "-m", commit_message], cwd=project_root)
                    if not commit_success:
                        print("Failed to commit changes. Skipping push for this cycle.", file=sys.stderr)
                        time.sleep(10)
                        continue

                    # Step 3: Push to origin current branch
                    success_branch, current_branch = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root)
                    if not success_branch:
                        print("Could not determine current branch. Aborting push.", file=sys.stderr)
                        time.sleep(10)
                        continue
                    
                    print(f"\n--- Running git push origin {current_branch} ---")
                    push_success, _ = run_command(["git", "push", "origin", current_branch], cwd=project_root)
                    if not push_success:
                        print("Failed to push changes.", file=sys.stderr)
                        print("Ensure you have configured Git credentials (e.g., SSH keys or credential helper).", file=sys.stderr)
                    else:
                        print("\n✅ Successfully added, committed, and pushed changes to GitHub!")
                else:
                    print("No commit message provided. Skipping commit and push for this cycle.")
            else:
                print(f"No changes detected. Checking again in 10 seconds...")

            time.sleep(10) # Wait for 10 seconds before checking again

        except KeyboardInterrupt:
            print("\nMonitoring stopped by user.")
            break
        except Exception as e:
            print(f"An unexpected error occurred in the main loop: {e}", file=sys.stderr)
            time.sleep(10) # Wait before retrying after an error

if __name__ == "__main__":
    auto_git_push()
