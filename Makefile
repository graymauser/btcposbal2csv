QUIET ?= -OO  # run with QUIET= to see debugging messages
CHAINSTATE ?= $(HOME)/.bitcoin/chainstate
BALANCES ?= balances.csv
PYTHON ?= python
ifeq ($(PYTHON),python3)
 PIP := pip3
else
 PIP := pip
endif
export
run: requirements.txt btcposbal2csv.py
	# stop bitcoind if running, to avoid corrupting chainstate
	$(PIP) install --user --requirement $<
	if $$(pidof bitcoind); then \
	 bitcoin-cli stop; \
	 $(PYTHON) $(QUIET) ./$(word 2, $+) $(CHAINSTATE) $(BALANCES); \
	 bitcoind; \
	else \
	 $(PYTHON) $(QUIET) ./$(word 2, $+) $(CHAINSTATE) $(BALANCES); \
	fi
requirements.txt:
	# WARNING: may be necessary to `sudo apt install libleveldb-dev`
	for requirement in plyvel base58 sqlite3 hashlib; do \
	 $(PYTHON) -c "import $$requirement" 2>/dev/null || \
	  (echo $$requirement >> $@; true); \
	done
