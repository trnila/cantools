import argparse
import random
import time
from collections.abc import Mapping
from typing import Any

import can

import cantools
import cantools.typechecking


def fuzz_signal(signal: cantools.db.Signal) -> Any:
    if signal.choices:
        return random.choice(list(signal.choices.values()))
    else:
        if signal.minimum is not None and signal.maximum is not None:
            return random.uniform(signal.minimum, signal.maximum)
        elif signal.is_signed:
            lim = 2**(signal.length - 1)
            return random.randint(-lim, lim - 1)
        else:
            return random.randint(0, 2**signal.length-1)

def fuzz_message(msg: cantools.db.Message) -> Mapping[str, Any]:
    data = {}
    for signal_item in msg.signal_tree:
        if isinstance(signal_item, str):
            signal = msg.get_signal_by_name(signal_item)
            data[signal.name] = fuzz_signal(signal)
        else:
            for selector_signal, choices in signal_item.items():
                selector = random.choice(list(choices.keys()))
                data[selector_signal] = selector

                for signal_name in choices[selector]:
                    signal = msg.get_signal_by_name(signal_name)
                    data[signal.name] = fuzz_signal(signal)

    return data

def fuzz(args: Any, values_format_specifier: str='') -> None:
    random.seed(0)
    db = cantools.db.load_file(args.database, strict=not args.no_strict)

    with can.Bus(args.bus, "socketcan", fd=True) as bus:
        while True:
            try:
                msg = random.choice(db.messages) # type: ignore
                if args.invalid:
                    raw_data = random.getrandbits(msg.length * 8).to_bytes(msg.length, 'little')
                else:
                    data: cantools.typechecking.EncodeInputType
                    if msg.is_container:
                        data = [(msg.name, fuzz_message(msg)) for msg in msg.contained_messages]
                    else:
                        data = fuzz_message(msg)

                    raw_data = msg.encode(data)

                is_fd = msg.is_fd
                if len(raw_data) > 8 and not is_fd:
                    # fix db maybe?
                    is_fd = True

                bus.send(can.Message(
                    arbitration_id=msg.frame_id,
                    is_fd=is_fd,
                    is_extended_id=msg.is_extended_frame,
                    data=raw_data,
                ))
                time.sleep(0.001)
            except Exception as e:
                print(e)


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        'fuzz',
        description=('Print the contents of a bus description file in an easy '
                     'to process and humanly readable format. This is similar '
                     'to "dump" with the output being less pretty but more '
                     'complete and much easier to process by shell scripts.'),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('bus')
    parser.add_argument('database', metavar='FILE')
    parser.add_argument('--invalid', action='store_true')
    parser.add_argument(
        '--no-strict',
        action='store_true',
        help='Skip database consistency checks.')
    parser.set_defaults(func=fuzz)
