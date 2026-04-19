import tkinter as tk

from gui.main_window import KinopubApp


def main():
    root = tk.Tk()
    app = KinopubApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
