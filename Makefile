QUIET ?= -OO  # run with QUIET= to see debugging messages
CHAINSTATE ?= $(HOME)/.bitcoin/chainstate
BALANCES ?= balances.csv
export
run: requirements.txt btcposbal2csv.py
	# stop bitcoind if running, to avoid corrupting chainstate
	pip3 install --user --requirement $<
	if $$(pidof bitcoind); then \
	 bitcoin-cli stop; \
	 python3 $(QUIET) ./$(word 2, $+) $(CHAINSTATE) $(BALANCES); \
	 bitcoind; \
	else \
	 python3 $(QUIET) ./$(word 2, $+) $(CHAINSTATE) $(BALANCES); \
	fi
requirements.txt:
	for requirement in plyvel base58 sqlite3 hashlib; do \
	 python3 -c "import $$requirement" 2>/dev/null || \
	  (echo $$requirement >> $@; true); \
	done
