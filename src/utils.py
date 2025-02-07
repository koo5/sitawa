def ctime_to_human(ctime):
	return time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(ctime))



def picsort(a, b):
	av = a[1]
	bv = b[1]
	a_dir = av[0]
	b_dir = bv[0]
	if a_dir == b_dir:
		return (1 if a[0] > b[0] else (-1 if a[0] < b[0] else 0))
	else:
		return 0



