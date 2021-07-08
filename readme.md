## Dump Bitcoin addresses with positive balance

Simple utility to list all bitcoin addresses with positive balance. It works by analysing the current unspent transaction output set (UTXO), aggregating outputs to same addresses together and write them to csv file.

#### Prequisities:  
python 2.7  
pip  

#### To install:  
run pip install -r requirements.txt

or install following packages with pip manualy

for linux：
* plyvel
* base58
* sqlite3

for winodws：
* plyvel-win32
* base58
* pysqlite3

#### Usage
To use you will need copy of chainstate database as created by [bitcoin core](https://bitcoin.org/en/bitcoin-core/)
 client. I've not tried different clients.
 
To get current addresses with positive balance, let the full node client sync with the network. 
**Stop** the bitcoin-core client before running this utility. If you not stop the client, the database might get corrupted.  
Then run this program with path to chainstate directory (usualy $HOME/.bitcoin/chainstate).

Show help
```
python btcposbal2csv.py -h
```
#### Example:  
Following will read from `/home/USER/.bitcoin/chainstate`, and write result to `/home/USER/addresses_with_balance.csv`.
```
python btcposbal2csv.py /home/USER/.bitcoin/chainstate /home/USER/addresses_with_balance.csv
```

##### Notice
* That the output may not be complete as there are some transactions which are not understood by the decoding lib, or that which do not have "address" at all. Such transactions are not processed. Number of them and the total ammount is displayed after the analysis.  
* The output csv file only reflects the chainstate leveldb at your disk. So it will always be few blocks behind the network as you need to stop the bitcoin-core client.

#### Converting to RIPEMD160
Per request, I'm adding script which is able to convert BTC address to RIPEMD160 representation.
BTC address must be in fist column, RIPEMD160 is added to csv. Output goes to stdout.

Example:
```
python convert2ripemd160.py /home/USER/addresses_with_balance.csv
```

#### Acknowledgement
This utility builds on very nice [bitcoin_tools](https://github.com/sr-gi/bitcoin_tools/) lib,
 which does the UTXO parsing.
#### Support
If you like this utility, please consider supporting the bitcoin_tools library which does all the heavy lifting.

If this particular functionality made your life easier you can support coffee consumption in BTC 
1FxC1mgJkad63beJcECfZMRaFSf4PBLr2f.
