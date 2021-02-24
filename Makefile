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
$(BALANCES): requirements.txt btcposbal2csv.py
	# stop bitcoind if running, to avoid corrupting chainstate
	$(PIP) install --user --requirement $<
	if pidof bitcoind >/dev/null; then \
	 bitcoin-cli stop; \
	 while pidof bitcoind >/dev/null; do sleep 1; done; \
	 $(PYTHON) $(QUIET) ./$(word 2, $+) $(CHAINSTATE) $(BALANCES)tmp; \
	 bitcoind; \
	else \
	 $(PYTHON) $(QUIET) ./$(word 2, $+) $(CHAINSTATE) $(BALANCES)tmp; \
	fi
	if [ "$$(wc -c $(BALANCES)tmp | awk '{print 1}')" -gt 1 ]; then \
	 mv $(BALANCES)tmp $(BALANCES); \
	else \
	 echo No balances found in chainstate >&2; \
	fi
requirements.txt:
	# WARNING: may be necessary to `sudo apt install libleveldb-dev`
	for requirement in plyvel base58 sqlite3 hashlib; do \
	 $(PYTHON) -c "import $$requirement" 2>/dev/null || \
	  (echo $$requirement >> $@; true); \
	done
