from hashlib import sha256
from re import match
import plyvel
from binascii import hexlify, unhexlify
from base58 import b58encode
import sys

# THIS functions are from bitcoin_tools and was only mildly changed.
# Please refer to readme.md for the proper link to that library.

# Fee per byte range
NSPECIALSCRIPTS = 6


def txout_decompress(x):
    """ Decompresses the Satoshi amount of a UTXO stored in the LevelDB. Code is a port from the Bitcoin Core C++
    source:
        https://github.com/bitcoin/bitcoin/blob/v0.13.2/src/compressor.cpp#L161#L185

    :param x: Compressed amount to be decompressed.
    :type x: int
    :return: The decompressed amount of satoshi.
    :rtype: int
    """

    if x == 0:
        return 0
    x -= 1
    e = x % 10
    x /= 10
    if e < 9:
        d = (x % 9) + 1
        x /= 9
        n = x * 10 + d
    else:
        n = x + 1
    while e > 0:
        n *= 10
        e -= 1
    return n


def b128_decode(data):
    """ Performs the MSB base-128 decoding of a given value. Used to decode variable integers (varints) from the LevelDB.
    The code is a port from the Bitcoin Core C++ source. Notice that the code is not exactly the same since the original
    one reads directly from the LevelDB.

    The decoding is used to decode Satoshi amounts stored in the Bitcoin LevelDB (chainstate). After decoding, values
    are decompressed using txout_decompress.

    The decoding can be also used to decode block height values stored in the LevelDB. In his case, values are not
    compressed.

    Original code can be found in:
        https://github.com/bitcoin/bitcoin/blob/v0.13.2/src/serialize.h#L360#L372

    Examples and further explanation can be found in b128_encode function.

    :param data: The base-128 encoded value to be decoded.
    :type data: hex str
    :return: The decoded value
    :rtype: int
    """

    n = 0
    i = 0
    while True:
        d = int(data[2 * i:2 * i + 2], 16)
        n = n << 7 | d & 0x7F
        if d & 0x80:
            n += 1
            i += 1
        else:
            return n


def parse_b128(utxo, offset=0):
    """ Parses a given serialized UTXO to extract a base-128 varint.

    :param utxo: Serialized UTXO from which the varint will be parsed.
    :type utxo: hex str
    :param offset: Offset where the beginning of the varint if located in the UTXO.
    :type offset: int
    :return: The extracted varint, and the offset of the byte located right after it.
    :rtype: hex str, int
    """

    data = utxo[offset:offset+2]
    offset += 2
    more_bytes = int(data, 16) & 0x80  # MSB b128 Varints have set the bit 128 for every byte but the last one,
    # indicating that there is an additional byte following the one being analyzed. If bit 128 of the byte being read is
    # not set, we are analyzing the last byte, otherwise, we should continue reading.
    while more_bytes:
        data += utxo[offset:offset+2]
        more_bytes = int(utxo[offset:offset+2], 16) & 0x80
        offset += 2

    return data, offset


def decode_utxo(coin, outpoint, version=0.15):
    """
    Decodes a LevelDB serialized UTXO for Bitcoin core v 0.15 onwards. The serialized format is defined in the Bitcoin
    Core source code as outpoint:coin.

    Outpoint structure is as follows: key | tx_hash | index.

    Where the key corresponds to b'C', or 43 in hex. The transaction hash in encoded in Little endian, and the index
    is a base128 varint. The corresponding Bitcoin Core source code can be found at:

    https://github.com/bitcoin/bitcoin/blob/ea729d55b4dbd17a53ced474a8457d4759cfb5a5/src/txdb.cpp#L40-L53

    On the other hand, a coin if formed by: code | value | out_type | script.

    Where code encodes the block height and whether the tx is coinbase or not, as 2*height + coinbase, the value is
    a txout_compressed base128 Varint, the out_type is also a base128 Varint, and the script is the remaining data.
    The corresponding Bitcoin Core soruce code can be found at:

    https://github.com/bitcoin/bitcoin/blob/6c4fecfaf7beefad0d1c3f8520bf50bb515a0716/src/coins.h#L58-L64

    :param coin: The coin to be decoded (extracted from the chainstate)
    :type coin: str
    :param outpoint: The outpoint to be decoded (extracted from the chainstate)
    :type outpoint: str
    :param version: Bitcoin Core version that created the chainstate LevelDB
    :return; The decoded UTXO.
    :rtype: dict
    """

    if 0.08 <= version < 0.15:
        return decode_utxo_v08_v014(coin)
    elif version < 0.08:
        raise Exception("The utxo decoder only works for version 0.08 onwards.")
    else:
        # First we will parse all the data encoded in the outpoint, that is, the transaction id and index of the utxo.
        # Check that the input data corresponds to a transaction.
        assert outpoint[:2] == '43'
        # Check the provided outpoint has at least the minimum length (1 byte of key code, 32 bytes tx id, 1 byte index)
        assert len(outpoint) >= 68
        # Get the transaction id (LE) by parsing the next 32 bytes of the outpoint.
        tx_id = outpoint[2:66]
        # Finally get the transaction index by decoding the remaining bytes as a b128 VARINT
        tx_index = b128_decode(outpoint[66:])

        # Once all the outpoint data has been parsed, we can proceed with the data encoded in the coin, that is, block
        # height, whether the transaction is coinbase or not, value, script type and script.
        # We start by decoding the first b128 VARINT of the provided data, that may contain 2*Height + coinbase
        code, offset = parse_b128(coin)
        code = b128_decode(code)
        height = code >> 1
        coinbase = code & 0x01

        # The next value in the sequence corresponds to the utxo value, the amount of Satoshi hold by the utxo. Data is
        # encoded as a B128 VARINT, and compressed using the equivalent to txout_compressor.
        data, offset = parse_b128(coin, offset)
        amount = txout_decompress(b128_decode(data))

        # Finally, we can obtain the data type by parsing the last B128 VARINT
        out_type, offset = parse_b128(coin, offset)
        out_type = b128_decode(out_type)

        if out_type in [0, 1]:
            data_size = 40  # 20 bytes
        elif out_type in [2, 3, 4, 5]:
            data_size = 66  # 33 bytes (1 byte for the type + 32 bytes of data)
            offset -= 2
        # Finally, if another value is found, it represents the length of the following data, which is uncompressed.
        else:
            data_size = (out_type - NSPECIALSCRIPTS) * 2  # If the data is not compacted, the out_type corresponds
            # to the data size adding the number os special scripts (nSpecialScripts).

        # And the remaining data corresponds to the script.
        script = coin[offset:]

        # Assert that the script hash the expected length
        assert len(script) == data_size

        # And to conclude, the output can be encoded. We will store it in a list for backward compatibility with the
        # previous decoder
        out = [{'amount': amount, 'out_type': out_type, 'data': script}]

    # Even though there is just one output, we will identify it as outputs for backward compatibility with the previous
    # decoder.
    return {'tx_id': tx_id, 'index': tx_index, 'coinbase': coinbase, 'outs': out, 'height': height}


def decode_utxo_v08_v014(utxo):
    """ Disclaimer: The internal structure of the chainstate LevelDB has been changed with Bitcoin Core v 0.15 release.
    Therefore, this function works for chainstate created with Bitcoin Core v 0.08-v0.14, for v 0.15 onwards use
    decode_utxo.

    Decodes a LevelDB serialized UTXO for Bitcoin core v 0.08 - v 0.14. The serialized format is defined in the Bitcoin
    Core source as follows:

     Serialized format:
     - VARINT(nVersion)
     - VARINT(nCode)
     - unspentness bitvector, for vout[2] and further; least significant byte first
     - the non-spent CTxOuts (via CTxOutCompressor)
     - VARINT(nHeight)

     The nCode value consists of:
     - bit 1: IsCoinBase()
     - bit 2: vout[0] is not spent
     - bit 4: vout[1] is not spent
     - The higher bits encode N, the number of non-zero bytes in the following bitvector.
        - In case both bit 2 and bit 4 are unset, they encode N-1, as there must be at
        least one non-spent output).

    VARINT refers to the CVarint used along the Bitcoin Core client, that is base128 encoding. A CTxOut contains the
    compressed amount of satoshi that the UTXO holds. That amount is encoded using the equivalent to txout_compress +
    b128_encode.

    :param utxo: UTXO to be decoded (extracted from the chainstate)
    :type utxo: hex str
    :return; The decoded UTXO.
    :rtype: dict
    """

    # Version is extracted from the first varint of the serialized utxo
    version, offset = parse_b128(utxo)
    version = b128_decode(version)

    # The next MSB base 128 varint is parsed to extract both is the utxo is coin base (first bit) and which of the
    # outputs are not spent.
    code, offset = parse_b128(utxo, offset)
    code = b128_decode(code)
    coinbase = code & 0x01

    # Check if the first two outputs are spent
    vout = [(code | 0x01) & 0x02, (code | 0x01) & 0x04]

    # The higher bits of the current byte (from the fourth onwards) encode n, the number of non-zero bytes of
    # the following bitvector. If both vout[0] and vout[1] are spent (v[0] = v[1] = 0) then the higher bits encodes n-1,
    # since there should be at least one non-spent output.
    if not vout[0] and not vout[1]:
        n = (code >> 3) + 1
        vout = []
    else:
        n = code >> 3
        vout = [i for i in xrange(len(vout)) if vout[i] is not 0]

    # If n is set, the encoded value contains a bitvector. The following bytes are parsed until n non-zero bytes have
    # been extracted. (If a 00 is found, the parsing continues but n is not decreased)
    if n > 0:
        bitvector = ""
        while n:
            data = utxo[offset:offset+2]
            if data != "00":
                n -= 1
            bitvector += data
            offset += 2

        # Once the value is parsed, the endianness of the value is switched from LE to BE and the binary representation
        # of the value is checked to identify the non-spent output indexes.
        bin_data = format(int(change_endianness(bitvector), 16), '0'+str(n*8)+'b')[::-1]

        # Every position (i) with a 1 encodes the index of a non-spent output as i+2, since the two first outs (v[0] and
        # v[1] has been already counted)
        # (e.g: 0440 (LE) = 4004 (BE) = 0100 0000 0000 0100. It encodes outs 4 (i+2 = 2+2) and 16 (i+2 = 14+2).
        extended_vout = [i+2 for i in xrange(len(bin_data))
                         if bin_data.find('1', i) == i]  # Finds the index of '1's and adds 2.

        # Finally, the first two vouts are included to the list (if they are non-spent).
        vout += extended_vout

    # Once the number of outs and their index is known, they could be parsed.
    outs = []
    for i in vout:
        # The satoshi amount is parsed, decoded and decompressed.
        data, offset = parse_b128(utxo, offset)
        amount = txout_decompress(b128_decode(data))
        # The output type is also parsed.
        out_type, offset = parse_b128(utxo, offset)
        out_type = b128_decode(out_type)
        # Depending on the type, the length of the following data will differ.  Types 0 and 1 refers to P2PKH and P2SH
        # encoded outputs. They are always followed 20 bytes of data, corresponding to the hash160 of the address (in
        # P2PKH outputs) or to the scriptHash (in P2PKH). Notice that the leading and tailing opcodes are not included.
        # If 2-5 is found, the following bytes encode a public key. The first byte in this case should be also included,
        # since it determines the format of the key.
        if out_type in [0, 1]:
            data_size = 40  # 20 bytes
        elif out_type in [2, 3, 4, 5]:
            data_size = 66  # 33 bytes (1 byte for the type + 32 bytes of data)
            offset -= 2
        # Finally, if another value is found, it represents the length of the following data, which is uncompressed.
        else:
            data_size = (out_type - NSPECIALSCRIPTS) * 2  # If the data is not compacted, the out_type corresponds
            # to the data size adding the number os special scripts (nSpecialScripts).

        # And finally the address (the hash160 of the public key actually)
        data, offset = utxo[offset:offset+data_size], offset + data_size
        outs.append({'index': i, 'amount': amount, 'out_type': out_type, 'data': data})

    # Once all the outs are processed, the block height is parsed
    height, offset = parse_b128(utxo, offset)
    height = b128_decode(height)
    # And the length of the serialized utxo is compared with the offset to ensure that no data remains unchecked.
    assert len(utxo) == offset

    return {'version': version, 'coinbase': coinbase, 'outs': outs, 'height': height}


def parse_ldb(fin_name, version=0.15, types=(0, 1)):
    counter = 0
    if 0.08 <= version < 0.15:
        prefix = b'c'
    elif version < 0.08:
        raise Exception("The utxo decoder only works for version 0.08 onwards.")
    else:
        prefix = b'C'

    # Open the LevelDB
    db = plyvel.DB(fin_name, compression=None)  # Change with path to chainstate

    # Load obfuscation key (if it exists)
    o_key = db.get((unhexlify("0e00") + "obfuscate_key"))

    # If the key exists, the leading byte indicates the length of the key (8 byte by default). If there is no key,
    # 8-byte zeros are used (since the key will be XORed with the given values).
    if o_key is not None:
        o_key = hexlify(o_key)[2:]

    # For every UTXO (identified with a leading 'c'), the key (tx_id) and the value (encoded utxo) is displayed.
    # UTXOs are obfuscated using the obfuscation key (o_key), in order to get them non-obfuscated, a XOR between the
    # value and the key (concatenated until the length of the value is reached) if performed).
    not_decoded = [0, 0]
    for key, o_value in db.iterator(prefix=prefix):
        key = hexlify(key)
        if o_key is not None:
            value = deobfuscate_value(o_key, hexlify(o_value))
        else:
            value = hexlify(o_value)

        # If the decode flag is passed, we also decode the utxo before storing it. This is really useful when running
        # a full analysis since will avoid decoding the whole utxo set twice (once for the utxo and once for the tx
        # based analysis)
        if version < 0.15:
            value = decode_utxo_v08_v014(value)
        else:
            value = decode_utxo(value, key, version)

        for out in value['outs']:
            # 0 --> P2PKH
            # 1 --> P2SH
            # 2 - 3 --> P2PK(Compressed keys)
            # 4 - 5 --> P2PK(Uncompressed keys)

            if counter % 100 == 0:
                sys.stdout.write('\r parsed transactions: %d' % counter)
                sys.stdout.flush()
            counter += 1

            if out['out_type'] == 0:
                if out['out_type'] not in types:
                    continue
                add = hash_160_to_btc_address(out['data'], 0)
                yield add, out['amount'], value['height']
            elif out['out_type'] == 1:
                if out['out_type'] not in types:
                    continue
                add = hash_160_to_btc_address(out['data'], 5)
                yield add, out['amount'], value['height']
            elif out['out_type'] in (2, 3, 4, 5):
                if out['out_type'] not in types:
                    continue
                add = 'P2PK'
                yield add, out['amount'], value['height']
            else:
                not_decoded[0] += 1
                not_decoded[1] += out['amount']

    print('\nunable to decode %d transactions' % not_decoded[0])
    print('totaling %d satoshi' % not_decoded[1])

    db.close()


def deobfuscate_value(obfuscation_key, value):
    """
    De-obfuscate a given value parsed from the chainstate.

    :param obfuscation_key: Key used to obfuscate the given value (extracted from the chainstate).
    :type obfuscation_key: str
    :param value: Obfuscated value.
    :type value: str
    :return: The de-obfuscated value.
    :rtype: str.
    """

    l_value = len(value)
    l_obf = len(obfuscation_key)

    # Get the extended obfuscation key by concatenating the obfuscation key with itself until it is as large as the
    # value to be de-obfuscated.
    if l_obf < l_value:
        extended_key = (obfuscation_key * ((l_value / l_obf) + 1))[:l_value]
    else:
        extended_key = obfuscation_key[:l_value]

    r = format(int(value, 16) ^ int(extended_key, 16), 'x')

    # In some cases, the obtained value could be 1 byte smaller than the original, since the leading 0 is dropped off
    # when the formatting.
    if len(r) is l_value-1:
        r = r.zfill(l_value)

    assert len(value) == len(r)

    return r


def change_endianness(x):
    """ Changes the endianness (from BE to LE and vice versa) of a given value.

    :param x: Given value which endianness will be changed.
    :type x: hex str
    :return: The opposite endianness representation of the given value.
    :rtype: hex str
    """

    # If there is an odd number of elements, we make it even by adding a 0
    if (len(x) % 2) == 1:
        x += "0"
    y = x.decode('hex')
    z = y[::-1]
    return z.encode('hex')


def hash_160_to_btc_address(h160, v):
    """ Calculates the Bitcoin address of a given RIPEMD-160 hash from an elliptic curve public key.

    :param h160: RIPEMD-160 hash.
    :type h160: bytes
    :param v: version (prefix) used to calculate the Bitcoin address.

     Possible values:

        - 0 for main network (PUBKEY_HASH).
        - 111 For testnet (TESTNET_PUBKEY_HASH).
    :type v: int
    :return: The corresponding Bitcoin address.
    :rtype: hex str
    """

    # If h160 is passed as hex str, the value is converted into bytes.
    if match('^[0-9a-fA-F]*$', h160):
        h160 = unhexlify(h160)

    # Add the network version leading the previously calculated RIPEMD-160 hash.
    vh160 = chr(v) + h160
    # Double sha256.
    h = sha256(sha256(vh160).digest()).digest()
    # Add the two first bytes of the result as a checksum tailing the RIPEMD-160 hash.
    addr = vh160 + h[0:4]
    # Obtain the Bitcoin address by Base58 encoding the result
    addr = b58encode(addr)

    return addr
