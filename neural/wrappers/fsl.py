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
    # Since BET fails on weirdly distributed datasets, I added 3dUnifize in... I realize this makes this dependent on AFNI. Sorry, :)
    out_dset = nl.suffix(dset,suffix)
    unifize_dset = nl.suffix(dset,'_u')
    cmd = bet2 if bet2 else 'bet2'
    info = nl.dset_info(dset)
    cmd = os.path.join(fsl_dir,cmd) if fsl_dir else cmd
    cutoff_value = info.subbricks[0]['max'] * 0.05
    nl.run(['3dUnifize','-prefix',unifize_dset,nl.calc(dset,'step(a-%f)*a' % cutoff_value)],products=unifize_dset)
    nl.run([cmd,unifize_dset,out_dset,'-w',0.25],products=out_dset)