import psutil
import tkinter as tk
from tkinter import messagebox
import socket
from enum import Enum
import asyncio

all_ports = {'http': 80, 'test API 1': 8080}

for i in range(1, 10):
    all_ports['test API ' + str(i + 2)] = 8080 + i

port_frames = {}

window = tk.Tk()
window.state('zoomed')
window.config(bg='gray7')
window.title('Port monitoring')
win_height = window.winfo_screenheight()
win_width = window.winfo_screenwidth()

main_frame = tk.Frame(window)
main_frame.config(bg='gray7')
main_frame.pack(fill='both', expand=1)

ports_canvas = tk.Canvas(main_frame)
ports_canvas.config(bg='gray7')
ports_canvas.pack(side='left', fill='both', expand=1)

ports_canvas_scrollbar = tk.Scrollbar(main_frame, orient='vertical', command=ports_canvas.yview)
ports_canvas_scrollbar.config(bg='gray7')
ports_canvas_scrollbar.pack(side='right', fill='y')

ports_canvas.configure(yscrollcommand=ports_canvas_scrollbar.set)
ports_canvas.bind(
    '<Configure>', lambda e: ports_canvas.configure(scrollregion=ports_canvas.bbox('all'))
)

ports_canvas_frame = tk.Frame(ports_canvas, bg='gray7')
ports_canvas.create_window((0, 0), window=ports_canvas_frame, anchor='nw')

def close_port(port):
    for conn in psutil.net_connections():
        if conn.laddr.port == port:
            try:
                # Terminate the process associated with the port
                psutil.Process(conn.pid).terminate()
            except psutil.NoSuchProcess:
                pass  # Process might have already terminated

def confirm_and_close_port(port):
    result = messagebox.askquestion("Confirmation", f"Do you want to close port {port}?")
    if result == 'yes':
        close_port(port)
        messagebox.showinfo("Port Closed", f"Port {port} closed successfully.")

class PortStatus(Enum):
    LISTENING = "Listening"
    ESTABLISHED = "Established"
    TIME_WAIT = "Time wait"
    CLOSE_WAIT = "Close wait"
    CLOSED = "Closed"
    ERROR = "Error"
    CLOSING = "Closing"

def get_font_colour_by_status(status):
    if status in [PortStatus.LISTENING.value, PortStatus.ESTABLISHED.value]:
        return 'lawn green'
    elif status in [PortStatus.CLOSED.value, PortStatus.ERROR.value]:
        return 'red3'
    elif status in [PortStatus.TIME_WAIT.value, PortStatus.CLOSE_WAIT.value, PortStatus.CLOSING.value]:
        return 'gold'
    else:
        return 'firebrick1'

def get_port_status(port):
    host = 'localhost'
    try:
        sock = socket.create_connection((host, port), timeout=1)
        sock.close()

        for conn in psutil.net_connections():
            if conn.laddr.port == port:
                if conn.status == psutil.CONN_LISTEN:
                    return PortStatus.LISTENING
                elif conn.status == psutil.CONN_ESTABLISHED:
                    return PortStatus.ESTABLISHED
                elif conn.status == psutil.CONN_TIME_WAIT:
                    return PortStatus.TIME_WAIT
                elif conn.status == psutil.CONN_CLOSE_WAIT:
                    return PortStatus.CLOSE_WAIT
                elif conn.status == psutil.CONN_CLOSING:
                    return PortStatus.CLOSING

        return PortStatus.CLOSED
    except (socket.timeout, ConnectionRefusedError):
        return PortStatus.CLOSED
    except Exception as e:
        return PortStatus.ERROR

async def get_port_status_async(port):
    loop = asyncio.get_event_loop()
    try:
        future = loop.run_in_executor(None, get_port_status, port)
        return await future
    except Exception as e:
        return PortStatus.ERROR

def update_port(name, port, i, ports_canvas_frame: tk.Frame, status):
    global port_frames
    if name not in port_frames.keys():
        port_frame = tk.Frame(ports_canvas_frame, bg='gray12', name=name)
        port_frame.grid(row=(int(i / 3)), column=(int(i % 3)), sticky='nsew', padx=int(win_width * 0.05), pady=int(win_height * 0.05))
        port_frames[name] = port_frame
        port_label = tk.Label(port_frame, text=name + ': ' + str(port), bg='gray12', foreground='gray77', font=('Courier', 20))
        port_label.grid(row=0, sticky='nsew')
        port_status = tk.Label(port_frame, text=status, bg='gray12', foreground='gray77', font=('Courier', 20))
        port_status.grid(row=1, sticky='nsew')
        if (status not in [PortStatus.CLOSED.value, PortStatus.CLOSING.value, PortStatus.ERROR.value]):
            port_close_button = tk.Button(port_frame, text="Close Port", command=lambda p=port: confirm_and_close_port(p))
            port_close_button.grid(row=2, pady=(10, 0))
    else:
        port_frame = port_frames[name]
        port_label: tk.Label = port_frame.winfo_children()[0]
        port_label.config(text=name + ': ' + str(port))
        port_status: tk.Label = port_frame.winfo_children()[1]
        port_status.config(text=status)
        if (status not in [PortStatus.CLOSED.value, PortStatus.CLOSING.value, PortStatus.ERROR.value] and not len(port_frame.winfo_children()) > 2):
            port_close_button = tk.Button(port_frame, text="Close Port", command=lambda p=port: confirm_and_close_port(p))
            port_close_button.grid(row=2, column=0, pady=(10, 0))
        elif (status in [PortStatus.CLOSED.value, PortStatus.CLOSING.value, PortStatus.ERROR.value] and len(port_frame.winfo_children()) > 2):
            port_frame.winfo_children()[2].destroy()

    port_status.config(foreground=get_font_colour_by_status(status))

async def update_ports(ports):
    global ports_canvas_frame, win_width, win_height

    window.update_idletasks()
    win_width = window.winfo_width()

    # Set the width of ports_canvas_frame to match ports_canvas
    ports_canvas.itemconfig('all', width=win_width - ports_canvas_scrollbar.winfo_width())

    # Create a set of current port names
    curr_port_names = set(ports.keys())

    # Iterate over the children and destroy those not in curr_ports
    for child in list(ports_canvas_frame.winfo_children()):
        if child.winfo_name() not in curr_port_names:
            child.destroy()

    i = 0
    tasks = [get_port_status_async(port) for port in ports.values()]
    statuses = await asyncio.gather(*tasks)

    for (name, port), status in zip(ports.items(), statuses):
        update_port(name, port, i, ports_canvas_frame, status.value)
        i += 1

    ports_canvas_frame.update()
    ports_canvas_frame.update_idletasks()

close_request = False

def on_closing():
    if messagebox.askokcancel("Quit", "Do you want to quit?"):
        global close_request
        close_request = True
        window.destroy()

async def main():
    window.protocol('WM_DELETE_WINDOW', on_closing)

    global close_request
    global curr_ports, all_ports
    curr_ports = all_ports
    print(curr_ports)
    while not close_request:
        await update_ports(curr_ports)
        await asyncio.sleep(1)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
