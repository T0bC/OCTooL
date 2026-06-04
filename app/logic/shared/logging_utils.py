"""
Error logging utilities (pure file I/O, tkinter-free).

Provides :func:`log_error_to_file`, which writes error details to a daily log
file under the project-root ``logs/`` directory.
"""
from datetime import datetime
import os


def _project_root():
    """Return the project root directory.

    This module lives at ``app/logic/shared/logging_utils.py`` (three packages
    deep), so the project root is four directory levels up.
    """
    return os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        )
    )


def log_error_to_file(function_name, args, kwargs, custom_message, traceback_text):
    """
    Logs error details to a daily log file in the project-root 'logs/' directory.

    Args:
        function_name (str): Name of the function where the error occurred.
        args (tuple): Positional arguments passed to the function.
        kwargs (dict): Keyword arguments passed to the function.
        custom_message (str): Optional custom error message.
        traceback_text (str): Full traceback string.
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    # Create logs directory at the project root (not the module directory).
    logs_dir = os.path.join(_project_root(), "logs")
    os.makedirs(logs_dir, exist_ok=True)

    log_filename = f"error_log_{date_str}.txt"
    log_path = os.path.join(logs_dir, log_filename)

    # Format arguments
    args_str = ", ".join(repr(a) for a in args)
    kwargs_str = ", ".join(f"{k}={repr(v)}" for k, v in kwargs.items())

    log_entry = (
        f"\n{'='*80}\n"
        f"🕒 Timestamp: {date_str} {time_str}\n"
        f"🔧 Function: {function_name}\n"
        f"📌 Message: {custom_message or 'Unhandled exception'}\n"
        f"🧩 Args: {args_str}\n"
        f"🧩 Kwargs: {kwargs_str}\n"
        f"{'-'*80}\n"
        f"{traceback_text}\n"
        f"{'='*80}\n"
    )

    with open(log_path, "a", encoding="utf-8") as log_file:
        log_file.write(log_entry)
