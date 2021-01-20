import base58
import binascii
import argparse
import bech32


def tocondensed(add_or_pk):
    return base58.b58decode(add_or_pk)[1:-4]


def process(csvfile):
    with open(csvfile, 'r') as f:
        for i, row in enumerate(f):
            if i == 0:
                print(row[:-1] + ',ripemd')
                continue
            elif row.strip() == '':
                break

            if row[:3].lower() == 'bc1':
                _, script_int = bech32.decode('bc', row.split(',')[0].lower())
                ripemd_encoded = binascii.hexlify(bytearray(script_int))
            else:
                ripemd_bin = tocondensed(row.split(',')[0])
                ripemd_encoded = binascii.hexlify(ripemd_bin)
            print(row[: -1] + ',' + ripemd_encoded.decode())


def input_args():
    parser = argparse.ArgumentParser(description='Read csv file with btc address as first column'\
                                     ' encodes it to ripemd160 binascii representation and writes to stdout'
                                     )
    parser.add_argument(
        'csvin',
        metavar='csv file',
        type=str,
        help='path to csv file with btc address in first column (usually output of btcposbal2csv)'
    )

    a = parser.parse_args()
    return a


if __name__ == '__main__':
    args = input_args()
    process(args.csvin)