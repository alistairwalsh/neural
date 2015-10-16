import os,shutil,tempfile,re,multiprocessing,copy
import neural as nl

class Decon:
    '''wrapper for AFNI 3dDeconvolve command
    
    Properties:
        :input_dset:        ``list`` of input datasets
        :decon_stims:       ``list`` of :class:`DeconStim` objects that define the different stimuli. Allows
                            for flexible coding of complex stimuli. Alternatively, for simpler stimuli, you 
                            can simply use one of the traditional options below (e.g., ``stim_files`` or ``stim_times``)
        :stim_files:        ``dict`` where keys are used as stimulus labels
                            and the values are taken as 1D files
        :stim_times:        same as stim_files, but used as a stim_times file
        :models:            ``dict`` of model names to use for each of the
                            listed stimuli (optional)
        :model_default:     default model to use for each ``stim_times`` stimulus if nothing
                            is listed in ``models``
        :stim_base:         ``list`` of names of stimuli (defined either in stim_files or 
                            stim_times) that should be considered in the baseline instead
                            of full model
        :stim_am1:          ``list`` of names of stimuli defined in stim_times that should
                            use the ``-stim_times_AM1`` model
        :stim_am2:          ``list`` of names of stimuli defined in stim_times that should
                            use the ``-stim_times_AM2`` model
        :glts:              ``dict`` where keys are GLT labels, and the value
                            is a symbolic statement
        :mask:              either a mask file, or "auto", which will use "-automask"
        :errts:             name of file to save residual time series to
        
        Options that are obvious:
            nfirst (default: 3), censor_file, polort (default: 'A'), tout, vout, rout, prefix
            
        opts        = list of extra things to put in the command
        
        **Example:**::
        
            decon = neural.decon.Decon()
            decon.input_dsets = ['dset_run1.nii.gz', 'dset_run2.nii.gz']
            decon.censor_file = 'subject_censor.1D'
            decon.stim_files = {
                'motion_1': 'motion_file.1D[0]',
                'motion_2': 'motion_file.1D[1]',
                'motion_3': 'motion_file.1D[2]',
                'motion_4': 'motion_file.1D[3]',
                'motion_5': 'motion_file.1D[4]',
                'motion_6': 'motion_file.1D[5]'
            }
            decon.stim_base = ['motion_%d' % i for i in range(1,7)]
            decon.stim_times = {
                'stim_a': 'stim_a.stimtimes',
                'stim_b': 'stim_b.stimtimes',
                'stim_c': 'stim_c.stimtimes',
            }
            decon.glts ={
                'a-b': '1*stim_a + -1*stim_b',
                'ab-c': '0.5*stim_a + 0.5*stim_b + -1*stim_c'
            }
            decon.prefix = 'subject_decon.nii.gz'
            decon.run()
    '''
    def __init__(self):
        self.input_dsets=[]
        self.stim_files={}
        self.stim_times={}
        self.decon_stims = []
        self.model_default = 'GAM'
        self.models = {}
        self.stim_base = []
        self.stim_am1 = []
        self.stim_am2 = []
        self.censor_file=None
        self.glts={}
        self.opts=[]
        self.nfirst = 3
        self.mask = 'auto'
        self.polort = 'A'
        self.prefix = None
        self.bout = True
        self.tout = True
        self.vout = True
        self.rout = True
        self.reps = None
        self.TR = None
        self.stim_sds = None
        self.errts = None
        
        self._del_files = []
    
    def command_list(self):
        '''returns the 3dDeconvolve command as a list
    
        The list returned can be run by passing it into a subprocess-like command
        (e.g., neural.run())
        '''
        cmd = ['3dDeconvolve']

        cmd += ['-jobs',multiprocessing.cpu_count()]
        cmd += self.opts
        if(len(self.input_dsets)):
            cmd += ['-input'] + self.input_dsets
        else:
            cmd += ['-nodata']
            if self.reps:
                cmd += [str(self.reps)]
                if self.TR:
                    cmd += [str(self.TR)]
        if self.censor_file:
            cmd += ['-censor', self.censor_file]
        cmd += ['-nfirst',str(self.nfirst)]
        if self.mask:
            if self.mask=='auto':
                cmd += ['-automask']
            else:
                cmd += ['-mask',self.mask]
        cmd += ['-polort',str(self.polort)]
        
        cmd += ['-num_stimts',len(self.stim_files)+len(self.stim_times)+len(self.decon_stims)]
        
        stim_num = 1
        
        all_stims = list(self.decon_stims)
        all_stims += [DeconStim(stim,column_file=self.stim_files[stim],base=(stim in self.stim_base)) for stim in self.stim_files]
        for stim in self.stim_times:
            decon_stim = DeconStim(stim,times_file=self.stim_times[stim])
            decon_stim.times_model = self.models[stim] if stim in self.models else self.model_default
            decon_stim.AM1 = (stim in self.stim_am1)
            decon_stim.AM2 = (stim in self.stim_am2)
            decon_stim.base = (stim in self.stim_base)
            all_stims.append(decon_stim)
            
        for stim in all_stims:        
            column_file = stim.column_file
            if stim.column!=None:
                with tempfile.NamedTemporaryFile(delete=False) as f:
                    f.write('\n'.join([str(x) for x in stim.column]))
                    column_file = f.name
                    self._del_files.append(f.name)
            if column_file:
                cmd += ['-stim_file',stim_num,column_file,'-stim_label',stim_num,stim.name]
                if stim.base:
                    cmd += ['-stim_base',stim_num]
                stim_num += 1
                continue
            times_file = stim.times_file
            if stim.times!=None:
                times = list(stim.times)
                if '__iter__' not in dir(times[0]):
                    # a single list
                    times = [times]
                with tempfile.NamedTemporaryFile(delete=False) as f:
                    f.write('\n'.join([' '.join([str(x) for x in y]) for y in times]))
                    times_file = f.name
                    self._del_files.append(f.name)
            if times_file:
                opt = '-stim_times'
                if stim.AM1:
                    opt = '-stim_times_AM1'
                if stim.AM2:
                    opt = '-stim_times_AM2'
                cmd += [opt,stim_num,times_file,stim.times_model]
                cmd += ['-stim_label',stim_num,stim.name]
                if stim.base:
                    cmd += ['-stim_base',stim_num]
                stim_num += 1
        
        cmd += ['-num_glt',len(self.glts)]
        
        glt_num = 1
        for glt in self.glts:
            cmd += ['-gltsym','SYM: %s' % self.glts[glt],'-glt_label',glt_num,glt]
            glt_num += 1
        
        if self.bout:
            cmd += ['-bout']
        if self.tout:
            cmd += ['-tout']
        if self.vout:
            cmd += ['-vout']
        if self.rout:
            cmd += ['-rout']
        
        if self.errts:
            cmd += ['-errts', self.errts]
        
        if self.prefix:
            cmd += ['-bucket', self.prefix]
        
        return [str(x) for x in cmd]
    
    def __del__(self):
        for f in self._del_files:
            try:
                os.unlink(f)
            except:
                pass
    
    def command_string(self):
        '''returns the 3dDeconvolve command as as string
        
        This command can then be run in something like a shell script
        '''
        return ' '.join(self.command_list())
    
    def run(self):
        '''runs 3dDeconvolve through the neural.utils.run shortcut'''
        out = nl.run(self.command_list(),products=self.prefix)
        # Not sure where the SDs went in the deconvolve output... but they aren't there for me now
        '''if out and out.output:
            stim_sds_list = [x.split() for x in out.output.strip().split('\n\n')]
            self.stim_sds = {}
            for stim in stim_sds_list:
                self.stim_sds[stim[1]] = float(stim[-1])'''

class DeconStim(object):
    '''encapsulates the definition of any arbitrary stimulus, along with all of its 3dDeconvolve options
    
    Attributes:
        :name:          Label used for the stimulus
        
        You only need to define one of the following to define the stimulus:
        :column:        A ``list`` of numbers (usually the length of the runs) that is placed directly in the 3dDeconvolve
                        matrix. This can be a series of 1's and 0's, a 1D-file that has already been convolved with an HRF,
                        or a covariate like motion parameters
        :column_file:   The filename of a file that contains a matrix column 
        :times:         Definition of stimuli using ``stim_times`` approach.  Either a ``list`` or a ``list`` of ``list``s
                        (one for each run) containing either ``float``s or strings of the stimulus times. For details on
                        how to define the stimulus time, see the documentation of ``3dDeconvolve``.
        :times_file:    A file containing a ``stim_times`` stimulus
        
        :times_model:   If using ``stim_times``, which HRF model to use
        :base:          Is this stimulus part of the baseline? (``True``/``False``)
        :AM1:           Does this stimulus use an "AM1" model? (``True``/``False``)
        :AM2:           Does this stimulus use an "AM2" model? (``True``/``False``)

        :reps:          Number of reps in associated fMRI run (helpful when manipulating the stims)
    
    '''
    def __init__(self,name,column_file=None,times_file=None,model='GAM',base=False,AM1=False,AM2=False):
        self.name = name
        self.column = None
        self.column_file = column_file
        self.times = None
        self.times_file = times_file
        self.times_model = model
        
        self.base = base
        self.AM1 = AM1
        self.AM2 = AM2

        self.reps = None

    def type(self):
        '''returns kind of stim ("column" or "times"), based on what parameters are set'''
        if self.column!=None or self.column_file:
            return "column"
        if self.times!=None or self.times_file:
            return "times"
        return None

    def read_file(self):
        '''if this is stored in a file, read it into self.column'''
        if self.column_file:
            with open(self.column_file) as f:
                self.column = [nl.numberize(x) for x in f.read().split('\n')]
        if self.times_file:
            with open(self.times_file) as f:
                self.times = [[nl.numberize(x) for x in y.split()] for y in f.read().split('\n')]

    def blank_stim(self,type=None,fill=0):
        '''Makes a blank version of stim. If a type is not given, returned as same type as current stim.
        If a column stim, will fill in blanks with ``fill``'''
        blank = copy.copy(self)
        blank.name = 'Blank'
        if type==None:
            type = self.type()
        if type=="column":
            num_reps = self.reps
            if num_reps==None:
                if self.type()=="column":
                    self.read_file()
                    num_reps = len(self.column)
                else:
                    nl.notify('Error: requested to return a blank column, but I can\'t figure out how many reps to make it!',level=nl.level.error)
            blank.column = [fill]*num_reps
            return blank
        if type=="times":
            blank.times = []
            return blank

    def concat_stim(self,decon_stim):
        '''concatenate this to another :class:`DeconStim` of the same "type"'''
        if self.type()!=decon_stim.type():
            nl.notify('Error: Trying to concatenate stimuli of different types! %s (%s) with %s (%s)' % (self.name,self.type(),decon_stim.name,decon_stim.type()),level=nl.level.error)
            return None
        concat_stim = copy.copy(self)
        if self.name=='Blank':
            concat_stim = copy.copy(decon_stim)

        self.read_file()
        if self.type()=="column":
            # if an explicit # of reps is given, concat to that
            reps = [x.reps if x.reps else len(x.column) for x in [self,decon_stim]]
            concat_stim.column = self.column[:reps[0]] + decon_stim.column[:reps[1]]
            return concat_stim
        if self.type()=="times":
            if len(self.times)==0 or '__iter__' not in dir(self.times[0]):
                self.times = [self.times]
            if len(decon_stim.times)==0 or '__iter__' not in dir(decon_stim.times[0]):
                decon_stim.times = [decon_stim.times]
            concat_stim.times = self.times + decon_stim.times
            return concat_stim
        return None
        
        def partial(self,start=0,end=None):
            '''chops the stimulus by only including time points ``start`` through ``end`` (in seconds, inclusive; ``None``=until the end)'''
            decon_stim = copy.copy(self)
            self.read_file()
            if self.type()=="column": 
                # Need to change times from seconds to TRs...
                if end==None:
                    pass
                decon_stim.column_file = None
                decon_stim.column = decon_stim.column[start]
                # ...
            if self.type()=="times":
                pass
                # ...
            return decon_stim

def smooth_decon_to_fwhm(decon,fwhm,cache=False):
    '''takes an input :class:`Decon` object and uses ``3dBlurToFWHM`` to make the output as close as possible to ``fwhm``
    returns the final measured fwhm. If ``cache`` is ``True``, will save the blurred input file (and use it again in the future)'''
    if os.path.exists(decon.prefix):
        return
    with nl.notify('Running smooth_decon_to_fwhm analysis (with %.2fmm blur)' % fwhm):
        tmpdir = tempfile.mkdtemp()
        try:
            cwd = os.getcwd()
            random_files = [re.sub(r'\[\d+\]$','',str(x)) for x in nl.flatten([x for x in decon.__dict__.values() if isinstance(x,basestring) or isinstance(x,list)]+[x.values() for x in decon.__dict__.values() if isinstance(x,dict)])]
            files_to_copy = [x for x in random_files if os.path.exists(x) and x[0]!='/']
            # copy crap
            for file in files_to_copy:
                try:
                    shutil.copytree(file,tmpdir)
                except OSError as e:
                    shutil.copy(file,tmpdir)
                shutil.copy(file,tmpdir)
            with nl.run_in(tmpdir):
                if os.path.exists(decon.prefix):
                    os.remove(decon.prefix)
                old_errts = decon.errts
                decon.errts = 'residual.nii.gz'
                decon.prefix = os.path.basename(decon.prefix)
                # Run once in place to get the residual dataset
                decon.run()
                running_reps = 0
                blur_input = lambda dset: 'input_blur-part%d.nii.gz'%(i+1)
                for i in xrange(len(decon.input_dsets)):
                    dset = decon.input_dsets[i]
                    info = nl.dset_info(dset)
                    residual_dset = 'residual-part%d.nii.gz'%(i+1)
                    nl.run(['3dbucket','-prefix',residual_dset,'%s[%d..%d]'%(decon.errts,running_reps,running_reps+info.reps-1)],products=residual_dset)
                    cmd = ['3dBlurToFWHM','-quiet','-input',dset,'-blurmaster',residual_dset,'-prefix',blur_input(i),'-FWHM',fwhm]
                    if decon.mask:
                        if decon.mask=='auto':
                            cmd += ['-automask']
                        else:
                            cmd += ['-mask',decon.mask]
                    nl.run(cmd,products=blur_input(i))
                    running_reps += info.reps
                decon.input_dsets = [blur_input(i) for i in xrange(len(decon.input_dsets))]
                for d in [decon.prefix,decon.errts]:
                    if os.path.exists(d):
                        try:
                            os.remove(d)
                        except:
                            pass
                decon.errts = old_errts
                decon.run()
                for copyfile in [decon.prefix,decon.errts]:
                    if os.path.exists(copyfile):
                        shutil.copy(copyfile,cwd)
                    else:
                        nl.notify('Warning: deconvolve did not produce expected file %s' % decon.prefix,level=nl.level.warning)
        except:
            raise
        finally:
            shutil.rmtree(tmpdir,True)