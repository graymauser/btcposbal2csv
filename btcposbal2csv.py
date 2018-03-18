import os
import tempfile
import argparse
import sqlite3
from utils import parse_ldb


def input_args():
    parser = argparse.ArgumentParser(description='Process UTXO set from chainstate and return unspent output per'
                                                 ' address for P2PKH and P2SH addresses')
    parser.add_argument(
        'chainstate',
        metavar='PATH_TO_CHAINSTATE_DIR',
        type=str,
        help='path to bitcoin chainstate directory (usually in full node data dir)'
    )
    parser.add_argument(
        '--bitcoin_version',
        type=float,
        default=0.15,
        help='versions of bitcoin node, acceptable values 0.08 - 0.15, default 0.15 should be OK'
    )
    parser.add_argument(
        'out',
        metavar='OUTFILE',
        type=str,
        default=None,
        help='output file in .csv'
    )
    parser.add_argument(
        '--keep_sqlite',
        metavar='PATH_TO_SQLITE_FILE)',
        type=str,
        default=None,
        help='output sqlite database file'
    )
    parser.add_argument(
        '--lowmem',
        action='store_true',
        help='use sqlite for aggregation of addresses instead of doing it in memory'
    )
    parser.add_argument(
        '--P2PKH',
        metavar='bool',
        type=bool,
        default=True,
        help='include P2PKH transactions, default 1'
    )
    parser.add_argument(
        '--P2SH',
        metavar='bool',
        type=bool,
        default=True,
        help='include P2PSH transactions, default 1'
    )
    parser.add_argument(
        '--P2PK',
        metavar='bool',
        type=bool,
        default=False,
        help='include P2PK transactions, default 0 '
             'warning - cannot decode address for this type of transactions, the total output'
             'for these addresses will be included under P2PK entry in output csv file'
    )
    parser.add_argument(
        '--sort',
        metavar='ASC/DESC',
        type=str,
        default=None,
        help='sort addresses by output ammount '
             'ASCending / DESCending '
             'if not given not sorting will be done'
    )
    a = parser.parse_args()

    if a.sort not in {None, 'ASC', 'DESC'}:
        raise AssertionError('--sort can be only "ASC" or "DESC"')

    if a.keep_sqlite and not a.lowmem:
        raise AssertionError('--keep_sqlite cannot be used with --lowmem')
    return a


def get_types(in_args):
    keep_types = set()
    if in_args.P2PKH:
        keep_types.add(0)
    if in_args.P2SH:
        keep_types.add(1)
    if in_args.P2PK:
        keep_types |= {2, 3, 4, 5}
    return keep_types


def in_mem(in_args):

    add_dict = dict()
    for add, val, height in parse_ldb(
            fin_name=in_args.chainstate,
            version=in_args.bitcoin_version,
            types=get_types(in_args)):
        if add in add_dict:
            add_dict[add][0] += val
            add_dict[add][1] = height
        else:
            add_dict[add] = [val, height]

    for key in add_dict.iterkeys():
        ll = add_dict[key]
        yield key, ll[0], ll[1]


def low_mem(in_args):
    keep_types = []
    if in_args.P2PKH:
        keep_types.append(0)
    if in_args.P2SH:
        keep_types.append(1)
    if in_args.P2PK:
        keep_types += [2, 3, 4, 5]

    if in_args.keep_sqlite:
        dbfile = in_args.keep_sqlite
    else:
        fd, dbfile = tempfile.mkstemp()
        os.close(fd)

    with sqlite3.connect(dbfile) as conn:
        curr = conn.cursor()

        curr.execute(
            """
            DROP TABLE IF EXISTS balance
            """
        )

        curr.execute(
            """
            CREATE TABLE balance (
                    address TEXT PRIMARY KEY,
                    amount BIGINT NOT NULL,
                    height BIGINT NOT NULL
            )
            """
        )

        curr.execute('BEGIN TRANSACTION')

        expinsert = """
            INSERT OR IGNORE INTO balance (address, amount, height) VALUES (?, ?, ?)"""
        expupdate = """
            UPDATE balance SET
            amount = amount + ?,
            height = ?
            WHERE address = ?
            """
        for add, val, height in parse_ldb(
                fin_name=in_args.chainstate,
                version=in_args.bitcoin_version,
                types=get_types(in_args)):
            curr.execute(expinsert, (add, 0, 0))
            curr.execute(expupdate, (val, height, add))

        if in_args.sort is None:
            exp = 'SELECT * FROM balance'
        elif in_args.sort == 'ASC':
            exp = 'SELECT * FROM balance ORDER BY amount ASC'
        elif in_args.sort == 'DESC':
            exp = 'SELECT * FROM balance ORDER BY amount DESC'
        else:
            raise Exception

        curr.execute(exp)

        for j in curr:
            yield j[0], j[1], j[2]

        conn.commit()
        curr.close()

    if not in_args.keep_sqlite:
        os.remove(dbfile)


if __name__ == '__main__':

    args = input_args()

    print('reading chainstate database')
    if args.lowmem:
        print('lowmem')
        add_iter = low_mem(args)
    else:
        print('inmem')
        add_iter = in_mem(args)

    if args.out:
        w = ['address,value_satoshi,last_height']
        with open(args.out, 'w') as f:
            c = 0
            for address, sat_val, block_height in add_iter:
                if sat_val == 0:
                    continue
                w.append(
                    address + ',' + str(sat_val) + ',' + str(block_height)
                )
                c += 1
                if c == 1000:
                    f.write('\n'.join(w) + '\n')
                    w = []
                    c = 0
            if c > 0:
                f.write('\n'.join(w) + '\n')
            f.write('\n')
        print('writen to %s' % args.out)
