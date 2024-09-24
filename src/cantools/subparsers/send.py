import argparse
from typing import Any

import can
from rich.pretty import pprint

import cantools
import cantools.database


def send(args: Any, values_format_specifier: str='') -> None:
    db = cantools.database.load_file(args.input_file_name)
    try:
        msg = db.get_message_by_name(args.msg) # type: ignore
    except KeyError:
        try:
            msg = db.get_message_by_frame_id(int(args.msg, 16)) # type: ignore
        except KeyError:
            print("Message not found, available messages:")
            print("\n".join([f'{m.frame_id:x} {m.name}' for m in db.messages])) # type: ignore
            exit(1)

    def get_default(s: cantools.database.Signal) -> Any:
        if s.initial:
            return s.initial
        return s.minimum

    data = {s.name: get_default(s) for s in msg.signals}
    for signal in args.signals:
        name, value = signal.split('=')
        if name not in data:
            print(f"Unknown signal {name}, available signals:")
            print("\n".join(data.keys()))
            exit(1)
        data[name] = float(value)

    pprint(data)

    with can.Bus(args.bus, 'socketcan') as bus:
        frame = can.Message(arbitration_id=msg.frame_id, data=msg.encode(data))
        if args.once:
            bus.send(frame)
        else:
            bus.send_periodic(frame, (msg.cycle_time or 100) / 1000)
            input()



def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    list_parser = subparsers.add_parser(
        'send',
        description=('Print the contents of a bus description file in an easy '
                     'to process and humanly readable format. This is similar '
                     'to "dump" with the output being less pretty but more '
                     'complete and much easier to process by shell scripts.'),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    list_parser.add_argument('bus')
    list_parser.add_argument('input_file_name', metavar='FILE')
    list_parser.add_argument('msg')
    list_parser.add_argument('signals', nargs='*')
    list_parser.add_argument('--once', '-1', action='store_true')
    list_parser.set_defaults(func=send)
