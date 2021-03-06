#!/usr/bin/env python
# 2D Slant stack for a single event
# Input is set of selected traces "*sel.mseed"
# traces have already been aligned and corrected for near-vertical statics
#   to have specified phase start at the earthquake origin time
# doesn't plot
# saves 2D stack "_2Dstack.mseed" and envelope of 2D stack "_2Dstack_env.mseed"
# John Vidale 2/2019

def pro5stack2d(eq_file, plot_scale_fac = 0.05, slow_delta = 0.0005,
			  slowR_lo = -0.1, slowR_hi = 0.1, slowT_lo = -0.1, slowT_hi = 0.1,
			  start_buff = -50, end_buff = 50, norm = 1, global_norm_plot = 1,
			  ARRAY = 0, NS = 0, decimate_fac = 0):

	from obspy import UTCDateTime
	from obspy import Stream, Trace
	from obspy import read
	from obspy.geodetics import gps2dist_azimuth
	import numpy as np
	import os
	from scipy.signal import hilbert
	import math
	import time

	import sys # don't show any warnings
	import warnings

	print('Running pro5b_stack2d')
	start_time_wc = time.time()

	if ARRAY == 0:
		file = open(eq_file, 'r')
	elif ARRAY == 1:
		goto = '/Users/vidale/Documents/PyCode/LASA/EvLocs'
		os.chdir(goto)
		file = open(eq_file, 'r')

	lines=file.readlines()
	split_line = lines[0].split()
#			ids.append(split_line[0])  ignore label for now
	t           = UTCDateTime(split_line[1])
	date_label  = split_line[1][0:10]
	ev_lat      = float(      split_line[2])
	ev_lon      = float(      split_line[3])
#	ev_depth    = float(      split_line[4])

	if not sys.warnoptions:
	    warnings.simplefilter("ignore")

#%% Get location file
	if ARRAY == 0: # Hinet set
		sta_file = '/Users/vidale/Documents/GitHub/Array_codes/Files/hinet_sta.txt'
		ref_lat = 36.3
		ref_lon = 138.5
	else:         # LASA set
		sta_file = '/Users/vidale/Documents/GitHub/Array_codes/Files/LASA_sta.txt'
		ref_lat = 46.69
		ref_lon = -106.22
	with open(sta_file, 'r') as file:
		lines = file.readlines()
	print(str(len(lines)) + ' stations read from ' + sta_file)
	# Load station coords into arrays
	station_index = range(len(lines))
	st_names = []
	st_lats  = []
	st_lons  = []
	for ii in station_index:
		line = lines[ii]
		split_line = line.split()
		st_names.append(split_line[0])
		st_lats.append( split_line[1])
		st_lons.append( split_line[2])

#%% Input parameters
	# date_label = '2018-04-02' # date for filename
	fname = 'HD' + date_label + 'sel.mseed'
	if ARRAY == 1:
		goto = '/Users/vidale/Documents/PyCode/LASA/Pro_Files'
		os.chdir(goto)

	st = Stream()
	st = read(fname)
	print('Read in: ' + str(len(st)) + ' traces')
	nt = len(st[0].data)
	dt = st[0].stats.delta
	print('First trace has : ' + str(nt) + ' time pts, time sampling of '
		  + str(dt) + ' and thus duration of ' + str((nt-1)*dt))

	#%% Make grid of slownesses
	slowR_n = int(1 + (slowR_hi - slowR_lo)/slow_delta)  # number of slownesses
	slowT_n = int(1 + (slowT_hi - slowT_lo)/slow_delta)  # number of slownesses
	stack_nt = int(1 + ((end_buff - start_buff)/dt))  # number of time points
	# In English, stack_slows = range(slow_n) * slow_delta - slow_lo
	a1R = range(slowR_n)
	a1T = range(slowT_n)
	stack_Rslows = [(x * slow_delta + slowR_lo) for x in a1R]
	stack_Tslows = [(x * slow_delta + slowT_lo) for x in a1T]
	print(str(slowR_n) + ' radial slownesses, ' + str(slowT_n) + ' trans slownesses, ')

#%% Build empty Stack array
	stack = Stream()
	tr = Trace()
	tr.stats.delta = dt
	tr.stats.starttime = t + start_buff
	tr.stats.npts = stack_nt
	tr.stats.network = 'stack'
	tr.stats.channel = 'BHZ'
	tr.data = np.zeros(stack_nt)
	done = 0
	for stackR_one in stack_Rslows:
		for stackT_one in stack_Tslows:
			tr1 = tr.copy()
			tr1.stats.station = str(int(done))
			stack.extend([tr1])
			done += 1

	#  Only need to compute ref location to event distance once
	ref_dist_az = gps2dist_azimuth(ev_lat,ev_lon,ref_lat,ref_lon)
#	ref_dist    = ref_dist_az[0]/1000  # km
	ref_back_az = ref_dist_az[2]
#	print(f'Ref location {ref_lat:.4f} , {ref_lon:.4f}, event location {ev_lat:.4f}  {ev_lon:.4f} ref_back_az  {ref_back_az:.1f}°')

#%% select by distance, window and adjust start time to align picked times
	done = 0
	for tr in st: # traces one by one, find lat-lon by searching entire inventory.  Inefficient but cheap
		for ii in station_index:
			if ARRAY == 0:  # have to chop off last letter, always 'h'
				this_name = st_names[ii]
				this_name_truc = this_name[0:5]
				name_truc_cap  = this_name_truc.upper()
			elif ARRAY == 1:
				name_truc_cap = st_names[ii]
			if (tr.stats.station == name_truc_cap): # find station in inventory
#			if (tr.stats.station == st_names[ii]): # found station in inventory
				if norm == 1:
					tr.normalize() # trace divided abs(max of trace)
				stalat = float(st_lats[ii])
				stalon = float(st_lons[ii]) # use lat & lon to find distance and back-az
				rel_dist_az = gps2dist_azimuth(stalat,stalon,ref_lat,ref_lon)
				rel_dist    = rel_dist_az[0]/1000  # km
				rel_back_az = rel_dist_az[1]       # radians

#				print(f'Sta lat-lon {stalat:.4f}  {stalon:.4f}')
				if NS == 0:
					del_distR = rel_dist * math.cos((rel_back_az - ref_back_az)* math.pi/180)
					del_distT = rel_dist * math.sin((rel_back_az - ref_back_az)* math.pi/180)
				# North and east
				else:
					del_distR = rel_dist * math.cos( rel_back_az * math.pi/180)
					del_distT = rel_dist * math.sin( rel_back_az * math.pi/180)
				for slowR_i in range(slowR_n):  # for this station, loop over radial slownesses
					for slowT_i in range(slowT_n):  # loop over transverse slownesses
						time_lag  = del_distR * stack_Rslows[slowR_i]  # time shift due to radial slowness
						time_lag += del_distT * stack_Tslows[slowT_i]  # time shift due to transverse slowness
						time_correction = ((t-tr.stats.starttime) + (time_lag + start_buff))/dt
						indx = int(slowR_i*slowT_n + slowT_i)
						for it in range(stack_nt):  # check points one at a time
							it_in = int(it + time_correction)
							if it_in >= 0 and it_in < nt - 2: # does data lie within seismogram?
								# should be 1, not 2, but 2 prevents the problem "index XX is out of bounds for axis 0 with size XX"
								stack[indx].data[it] += tr[it_in]
				done += 1
				if done%20 == 0:
					print('Done stacking ' + str(done) + ' out of ' + str(len(st)) + ' stations.')
#%% take envelope, decimate envelope
	stack_raw = stack.copy()
	for slowR_i in range(slowR_n):  # loop over radial slownesses
		for slowT_i in range(slowT_n):  # loop over transverse slownesses
			indx = slowR_i*slowT_n + slowT_i
			stack[indx].data = np.abs(hilbert(stack[indx].data))
			if decimate_fac != 0:
				stack[indx].decimate(decimate_fac)

#%%  Save processed files
	fname = 'HD' + date_label + '_2dstack_env.mseed'
	stack.write(fname,format = 'MSEED')

	fname = 'HD' + date_label + '_2dstack.mseed'
	stack_raw.write(fname,format = 'MSEED')

	elapsed_time_wc = time.time() - start_time_wc
	print('This job took ' + str(elapsed_time_wc) + ' seconds')
	os.system('say "Done"')