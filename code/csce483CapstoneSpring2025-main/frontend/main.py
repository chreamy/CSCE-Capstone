import tkinter as tk
from .app_controller import AppController


def main() -> None:
    root = tk.Tk()
    app = AppController(root)
    root.mainloop()


if __name__ == "__main__":
    main()
