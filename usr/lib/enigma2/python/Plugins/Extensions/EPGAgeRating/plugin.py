# EPGAgeRating - adds DVB parental rating info to OpenWebif's
# /api/epgservice (and epgservicenow / epgservicenext) JSON output.
#
# Works by wrapping OpenWebif's getChannelEpg() / getNowNextEpg()
# at runtime - no OpenWebif files are modified, so it survives
# OpenWebif updates (as long as the function names stay the same).
#
# Added field per event:
#   age_rating          -> minimum age in years (DVB value + 3), 0 = unrated
#
# Disabled (uncomment in _lookup_parental() to re-enable):
#   age_rating_raw      -> raw DVB rating value (1..15), 0 = unrated
#   age_rating_country  -> country code from the EIT parental descriptor
#
# License: GPLv2
#
from __future__ import print_function

from Plugins.Plugin import PluginDescriptor
from enigma import eEPGCache, eServiceReference, eTimer

PLUGIN_NAME = "EPGAgeRating"
PLUGIN_VERSION = "1.0"

_retry_timer = None
_retries_left = 30  # try for ~5 minutes (30 x 10s) waiting for OpenWebif


def _log(msg):
	print("[%s] %s" % (PLUGIN_NAME, msg))


def _lookup_parental(sref, event_id):
	"""Return dict with age rating info for one event (never raises)."""
	out = {"age_rating": 0}
	# out["age_rating_raw"] = 0
	# out["age_rating_country"] = ""
	try:
		if not sref or not event_id:
			return out
		epgcache = eEPGCache.getInstance()
		evt = epgcache.lookupEventId(eServiceReference(str(sref)), int(event_id))
		if evt is None:
			return out
		pdata = evt.getParentalData()
		if pdata is None:
			return out
		raw = 0
		country = ""
		try:
			raw = pdata.getRating()
		except Exception:
			pass
		try:
			country = pdata.getCountryCode() or ""
		except Exception:
			pass
		# out["age_rating_raw"] = raw
		# out["age_rating_country"] = country
		# DVB (ETSI EN 300 468): 0x01..0x0F => minimum age = value + 3
		# 0x00 = undefined, 0x10..0xFF = broadcaster defined (passed through raw)
		if 0 < raw <= 15:
			out["age_rating"] = raw + 3
		elif raw > 15:
			out["age_rating"] = raw
	except Exception as e:
		_log("parental lookup failed: %r" % e)
	return out


def _enrich_events(events):
	if not events:
		return
	for ev in events:
		try:
			if not isinstance(ev, dict):
				continue
			sref = ev.get("sref")
			eid = ev.get("id")
			ev.update(_lookup_parental(sref, eid))
		except Exception:
			pass


def _make_wrapper(orig):
	def wrapped(*args, **kwargs):
		res = orig(*args, **kwargs)
		try:
			if isinstance(res, dict):
				_enrich_events(res.get("events"))
		except Exception as e:
			_log("enrich failed: %r" % e)
		return res
	wrapped.__epg_age_rating_patched__ = True
	wrapped.__wrapped_orig__ = orig
	return wrapped


def _patch_symbol(module, name):
	"""Wrap module.<name> if present and not already wrapped."""
	fn = getattr(module, name, None)
	if fn is None or not callable(fn):
		return False
	if getattr(fn, "__epg_age_rating_patched__", False):
		return True
	setattr(module, name, _make_wrapper(fn))
	return True


def _try_patch():
	"""
	Patch getChannelEpg (backs epgservice) and getNowNextEpg
	(backs epgservicenow / epgservicenext) in every OpenWebif module
	that holds a reference to them.
	"""
	import importlib

	target_names = ("getChannelEpg", "getNowNextEpg")
	# models.services defines them; web/ajax import them by name,
	# so their module-level references must be re-bound too.
	module_paths = (
		"Plugins.Extensions.OpenWebif.controllers.models.services",
		"Plugins.Extensions.OpenWebif.controllers.web",
		"Plugins.Extensions.OpenWebif.controllers.ajax",
	)

	patched_any = False
	found_openwebif = False
	for path in module_paths:
		try:
			mod = importlib.import_module(path)
			found_openwebif = True
		except Exception:
			continue
		for name in target_names:
			if _patch_symbol(mod, name):
				patched_any = True
				_log("patched %s.%s" % (path, name))

	if not found_openwebif:
		_log("OpenWebif not (yet) importable")
	return patched_any


def _retry(session=None):
	global _retry_timer, _retries_left
	if _try_patch():
		_log("active - age_rating now included in /api/epgservice")
		_retry_timer = None
		return
	_retries_left -= 1
	if _retries_left <= 0:
		_log("giving up - OpenWebif not found")
		_retry_timer = None
		return
	if _retry_timer is None:
		_retry_timer = eTimer()
		_retry_timer.callback.append(_retry)
	_retry_timer.startLongTimer(10)


def autostart(reason, **kwargs):
	if reason == 0:  # enigma2 start
		_retry()


def main(session, **kwargs):
	# manual start from plugin browser: just (re)apply the patch and report
	from Screens.MessageBox import MessageBox
	ok = _try_patch()
	txt = ("EPGAgeRating is active.\n\n'age_rating' is included in "
		"/api/epgservice JSON output.") if ok else (
		"OpenWebif was not found - is it installed and started?")
	session.open(MessageBox, txt, MessageBox.TYPE_INFO, timeout=10)


def Plugins(**kwargs):
	return [
		PluginDescriptor(
			name=PLUGIN_NAME,
			description="Add DVB age rating to OpenWebif epgservice API",
			where=PluginDescriptor.WHERE_AUTOSTART,
			fnc=autostart,
			needsRestart=False,
		),
		PluginDescriptor(
			name=PLUGIN_NAME,
			description="Add DVB age rating to OpenWebif epgservice API",
			where=PluginDescriptor.WHERE_PLUGINMENU,
			icon="plugin.png",
			fnc=main,
			needsRestart=False,
		),
	]
