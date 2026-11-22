# GENERATO da tools/kernel_slot_scaffold.py — NON modificare lo scheletro.
obj-m += {name}.o

all:
	make -C /lib/modules/$(shell uname -r)/build M=$(PWD) modules

clean:
	make -C /lib/modules/$(shell uname -r)/build M=$(PWD) clean
