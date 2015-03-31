import neural as nl
import os

fsl_dir = None

# Try to find bet
bet2 = nl.which('bet2')
if bet2==None:
    bet2 = nl.which('fsl5.0-bet2')

def binary_available():
    if nl.which(bet2):
        return True

def skull_strip(dset,suffix='_ns'):
    ''' use bet to strip skull from given anatomy '''
    # should add options to use betsurf and T1/T2 in the future
    out_dset = nl.suffix(dset,suffix)
    cmd = bet2 if bet2 else 'bet2'
    cmd = os.path.join(fsl_dir,cmd) if fsl_dir else cmd
    nl.run([cmd,dset,out_dset],products=out_dset)