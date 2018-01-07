## Dump Bitcoin addresses with positive balance

Simple utility to extract bitcoin addresses with positive balance from current UTXO set, aggregate outputs to addresses
and write them to csv file.

####Prequisities:  
python 2.7  
pip  

####To install:  
run pip install -r requirements.txt

or install following packages with pip manualy
* hashlib
* plyvel
* base58
* sqlite3

####Usage
To use you will need copy of chainstate database as created by [bitcoin core](https://bitcoin.org/en/bitcoin-core/)
 client.
 
To get current addresses with positive balance, let the full node client sync with the network. 
**Stop** the client before running this utility. 
Then run this program with path to chainstate directory (usualy $HOME/.bitcoin/chainstate).

Show help
```
python btcposbal2csv.py -h

```
####Example:  
Following will read from `/home/USER/.bitcoin/chainstate`, and write result to `/home/USER/addresses_with_balance.csv`.
```
python btcposbal2csv.py /home/USER/.bitcoin/chainstate /home/USER/addresses_with_balance.csv
```

#####Notice
That the output may not be complete as there are some transactions which are not understood by the decoding lib.  
The output csv file only reflects the chainstate leveldb. So it will always be few blocks behind the network. 


####Acknowledgement
This utility builds on very nice [bitcoin_tools](https://github.com/sr-gi/bitcoin_tools/) lib,
 which does the UTXO parsing.
####Support
If you like this utility, please consider supporting the bitcoin_tools library which does all the heavy lifting.

If this particular functionality made your life easier you can support coffee consumption 
1FxC1mgJkad63beJcECfZMRaFSf4PBLr2f.
