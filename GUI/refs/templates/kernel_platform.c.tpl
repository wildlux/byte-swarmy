/* GENERATO da tools/kernel_slot_scaffold.py — NON modificare lo scheletro. */
/* Riempire SOLO i blocchi marcati SLOT_*: una funzione piccola alla volta.   */
/* Ogni simbolo kernel usato nei slot deve superare CORE/kernel_api_whitelist */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/fs.h>
#include <linux/platform_device.h>

#define DRV_NAME "{name}"

/* SLOT_READ: restituire dati all'utente — API di copia da verificare prima. */
static ssize_t {name}_read(struct file *filp, char __user *buf,
                           size_t count, loff_t *offp)
{{
    /* SLOT_READ — ritornare byte copiati oppure -EFAULT */
    return -ENOSYS;
}}

/* SLOT_WRITE: ricevere dati dall'utente — API di copia da verificare prima. */
static ssize_t {name}_write(struct file *filp, const char __user *buf,
                            size_t count, loff_t *offp)
{{
    /* SLOT_WRITE — ritornare byte copiati oppure -EFAULT */
    return -ENOSYS;
}}

/* SLOT_IOCTL: solo comandi semplici; verificare ogni simbolo prima dell'uso. */
static long {name}_ioctl(struct file *filp, unsigned int cmd, unsigned long arg)
{{
    /* SLOT_IOCTL — non inventare comandi o API */
    return -ENOTTY;
}}

/* Scheletro deterministico: probe/remove/file_operations NON vanno riscritti. */
static struct file_operations {name}_fops = {{
    .owner = THIS_MODULE,
    .read = {name}_read,
    .write = {name}_write,
    .unlocked_ioctl = {name}_ioctl,
}};

static int {name}_probe(struct platform_device *pdev)
{{
    dev_info(&pdev->dev, "{name}: probe\\n");
    return 0;
}}

static int {name}_remove(struct platform_device *pdev)
{{
    dev_info(&pdev->dev, "{name}: remove\\n");
    return 0;
}}

static struct platform_driver {name}_driver = {{
    .probe = {name}_probe,
    .remove = {name}_remove,
    .driver = {{ .name = DRV_NAME }},
}};

static int __init {name}_init(void)
{{
    return platform_driver_register(&{name}_driver);
}}

static void __exit {name}_exit(void)
{{
    platform_driver_unregister(&{name}_driver);
}}

module_init({name}_init);
module_exit({name}_exit);
MODULE_LICENSE("GPL");
