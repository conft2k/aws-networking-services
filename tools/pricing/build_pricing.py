#!/usr/bin/env python3
"""Build pricing/data.json for the AWS networking price table page.

Source: AWS Price List bulk API (public, no auth)
  https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json

Offers used: AWSDirectConnect, AWSCloudWAN, AmazonVPC (incl. VPC Lattice, IPAM, Traffic Mirroring,
Reachability Analyzer, Network Access Analyzer, Encryption Controls), AWSDataTransfer, AWSGlobalAccelerator,
AWSELB, AmazonApiGateway, AmazonCloudFront, CloudFrontPlans, AWSInterconnect, AmazonRoute53,
AWSNetworkFirewall, awswaf, AWSShield, AWSFMS, AmazonCloudWatch (vended logs, Network Flow Monitor,
Network Synthetic Monitor, custom metrics).
Per-region offer files are downloaded into a cache directory outside the repo, filtered
by productFamily / usagetype / attributes, and reduced to On-Demand USD prices.

NAT gateway prices live in the AmazonEC2 offer (~9 GB of region files), so they are taken from the
JSON that the official VPC pricing page loads (b0.p.awsstatic.com .../ec2/USD/current/natgateway.json)
and marked as source "pricing page" in data.json.

Usage (stdlib only):
  python3 -I tools/pricing/build_pricing.py [--cache DIR] [--refresh] [--out pricing/data.json]
"""
import argparse
import collections
import datetime as dt
import json
import os
import re
import sys
import urllib.request

BASE = 'https://pricing.us-east-1.amazonaws.com'
DEFAULT_CACHE = '/tmp/claude-1000/-home-ec2-user-mydev/efa2e064-b184-4982-b7ba-c281fe24d394/scratchpad/pricecache'
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OFFERS = ['AWSDirectConnect', 'AWSCloudWAN', 'AmazonVPC', 'AWSDataTransfer', 'AWSGlobalAccelerator', 'AWSELB',
          'AmazonApiGateway', 'AmazonCloudFront', 'CloudFrontPlans', 'AWSInterconnect', 'AmazonRoute53',
          'AWSNetworkFirewall', 'awswaf', 'AWSShield', 'AWSFMS', 'AmazonCloudWatch']
# offers whose global / edge SKUs are published in the pseudo region file "aws-other"
GLOBAL_FILE = {'AmazonCloudFront', 'CloudFrontPlans', 'AmazonRoute53', 'awswaf', 'AWSShield', 'AWSFMS', 'AmazonCloudWatch'}
PAGE_BASE = 'https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps'

# Commercial AWS Region codes look like "ap-northeast-2". Local Zones / Wavelength Zones
# ("us-east-1-scl-1") and pseudo regions ("aws-other") do not match.
REGION_RE = re.compile(r'^[a-z]{2}-[a-z]+-\d$')
EXCLUDED_PREFIXES = ('us-gov-', 'cn-', 'us-iso', 'eusc-')   # GovCloud, China, ISO, European Sovereign Cloud
EXCLUDED_RE = re.compile(r'^(us-gov|cn|us-iso[a-z]?|eusc)-[a-z]+-\d$')

# Display order (Excel-like): Asia Pacific (Seoul first), Middle East, Africa, Europe, Canada, US, Latin America.
GEO = [
    ('ap', 'Asia Pacific', ['ap-northeast-2', 'ap-northeast-1', 'ap-northeast-3', 'ap-east-1', 'ap-east-2',
                            'ap-southeast-1', 'ap-southeast-3', 'ap-southeast-5', 'ap-southeast-7',
                            'ap-south-1', 'ap-south-2', 'ap-southeast-2', 'ap-southeast-4', 'ap-southeast-6']),
    ('me', 'Middle East', ['me-central-1', 'me-south-1', 'il-central-1']),
    ('af', 'Africa', ['af-south-1']),
    ('eu', 'Europe', ['eu-central-1', 'eu-central-2', 'eu-west-1', 'eu-west-2', 'eu-west-3',
                      'eu-south-1', 'eu-south-2', 'eu-north-1']),
    ('ca', 'Canada', ['ca-central-1', 'ca-west-1']),
    ('us', 'United States', ['us-east-1', 'us-east-2', 'us-west-1', 'us-west-2']),
    ('la', 'Latin America', ['mx-central-1', 'sa-east-1']),
]
GEO_BY_PREFIX = {'ap': 'ap', 'me': 'me', 'il': 'me', 'af': 'af', 'eu': 'eu', 'ca': 'ca', 'us': 'us', 'mx': 'la', 'sa': 'la'}


# ---------------------------------------------------------------- download / cache
def fetch(url, path, refresh):
    if os.path.exists(path) and not refresh:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.part'
    with urllib.request.urlopen(url, timeout=300) as r, open(tmp, 'wb') as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    os.replace(tmp, path)
    return path


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def wanted_region_file(offer, code):
    if offer == 'AWSGlobalAccelerator':
        return True                          # single global file (aws-other)
    if offer == 'AWSDirectConnect':
        # DTO to a DX location is published in the file of the location's home Region / Local Zone,
        # and SiteLink data transfer lives in aws-other, so every DX file is needed (~95 MB).
        # Source Regions are filtered to commercial Regions later.
        return True
    if code == 'aws-other' and offer in GLOBAL_FILE:
        return True
    return bool(REGION_RE.match(code)) and not EXCLUDED_RE.match(code)


def offer_files(cache, refresh):
    idx = load(fetch(BASE + '/offers/v1.0/aws/index.json', os.path.join(cache, 'index.json'), refresh))
    meta, files, excluded = {}, {}, set()
    for o in OFFERS:
        ri = load(fetch(BASE + idx['offers'][o]['currentRegionIndexUrl'], os.path.join(cache, 'ri_%s.json' % o), refresh))
        urls = {k: v['currentVersionUrl'] for k, v in ri['regions'].items()}
        version = next(iter(urls.values())).split('/')[5]
        meta[o] = {'publicationDate': ri.get('publicationDate'), 'version': version,
                   'source': BASE + idx['offers'][o]['currentRegionIndexUrl']}
        files[o] = {}
        for code, u in sorted(urls.items()):
            if EXCLUDED_RE.match(code):
                excluded.add(code)
            if not wanted_region_file(o, code):
                continue
            files[o][code] = fetch(BASE + u, os.path.join(cache, o, code + '.json'), refresh)
    return idx, meta, files, sorted(excluded)


# ---------------------------------------------------------------- price helpers
TODAY = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def ondemand(doc, sku):
    """Return list of price dimensions [{usd, unit, begin, end, desc}] of the current OnDemand term."""
    terms = list(doc['terms'].get('OnDemand', {}).get(sku, {}).values())
    if not terms:
        return []
    live = [t for t in terms if t.get('effectiveDate', '') <= TODAY] or terms
    t = max(live, key=lambda t: t.get('effectiveDate', ''))
    dims = []
    for pd in t['priceDimensions'].values():
        usd = pd['pricePerUnit'].get('USD')
        if usd is None:
            continue
        end = pd.get('endRange')
        dims.append({'usd': float(usd), 'unit': pd.get('unit'), 'begin': float(pd.get('beginRange') or 0),
                     'end': None if end in (None, 'Inf') else float(end), 'desc': pd.get('description', '')})
    dims.sort(key=lambda d: d['begin'])
    return dims


def one(doc, sku):
    dims = ondemand(doc, sku)
    return round(dims[0]['usd'], 6) if dims else None


def tiers(doc, sku):
    return [[d['begin'], d['end'], round(d['usd'], 6)] for d in ondemand(doc, sku)]


def products(doc):
    for sku, p in doc['products'].items():
        yield sku, p.get('productFamily'), p['attributes']


def region_list(files_by_code, names):
    """Ordered [{code,name,geo}] for the given region codes."""
    codes = [c for c in files_by_code if REGION_RE.match(c)]
    known = [c for _, _, lst in GEO for c in lst]
    out = []
    for g, _, lst in GEO:
        extra = sorted(c for c in codes if c not in known and GEO_BY_PREFIX.get(c.split('-')[0]) == g)
        for c in lst + extra:
            if c in codes:
                out.append({'code': c, 'name': names.get(c, c), 'geo': g})
    return out


def mode(values):
    c = collections.Counter(values)
    return c.most_common(1)[0][0] if c else None


# ---------------------------------------------------------------- VPC family (TGW, VPN, PrivateLink, IPv4)
def build_vpc(files):
    names, tgw, vpn, pl, ipv4, cvpn, notes = {}, [], [], [], [], [], []
    for code, path in files.items():
        doc = load(path)
        rec = collections.defaultdict(dict)
        for sku, fam, a in products(doc):
            if a.get('locationType') != 'AWS Region':
                continue
            names[code] = a.get('location')
            u, op, grp = a.get('usagetype', ''), a.get('operation', ''), a.get('group', '')
            if grp == 'AWSTransitGateway':
                if u.endswith('TransitGateway-Hours'):
                    rec['tgw_hours'][op] = one(doc, sku)
                elif u.endswith('TransitGateway-Bytes'):
                    rec['tgw_bytes'][op] = one(doc, sku)
                elif u.endswith('TGW-Multicast-Consumer-Bytes'):
                    rec['tgw']['mcast'] = one(doc, sku)
            elif fam == 'Cloud Connectivity' and a.get('endpointType') == 'IPsec':
                rec['vpn'][a.get('vpnType')] = one(doc, sku)
            elif grp == 'AWSClientVPN':
                rec['cvpn']['endpoint' if 'EndpointHours' in u else 'conn'] = one(doc, sku)
            elif grp == 'VPCPublicIPv4Address':
                rec['ipv4']['inuse' if 'InUse' in u else 'idle'] = one(doc, sku)
            elif fam == 'VpcEndpoint' or grp == 'VpcResources':
                k = u.split('-', 1)[1]
                if k == 'VpcEndpoint-Hours':
                    rec['pl']['ep'] = one(doc, sku)
                elif k == 'VpcEndpoint-Bytes':
                    rec['pl']['epGb'] = tiers(doc, sku)
                elif k == 'VpcEndpoint-GWLBE-Hours':
                    rec['pl']['gwlbe'] = one(doc, sku)
                elif k == 'VpcEndpoint-GWLBE-Bytes':
                    rec['pl']['gwlbeGb'] = one(doc, sku)
                elif k == 'VpcEndpoint-Resource-Hours':
                    rec['pl']['res'] = one(doc, sku)
                elif k == 'VpcResource-Consumer-Bytes':
                    rec['pl']['resGb'] = tiers(doc, sku)
                elif k == 'VpcEndpoint-Service-Hours':
                    rec['pl']['remote'] = one(doc, sku)
        if code not in names:
            continue
        h, b = rec['tgw_hours'], rec['tgw_bytes']
        if h:
            others = {k: v for k, v in h.items() if v != h.get('TransitGatewayVPC')}
            if others:
                notes.append('TGW %s: attachment hour differs by type %s' % (code, others))
            tgw.append({'r': code, 'h': h.get('TransitGatewayVPC'), 'gb': b.get('TransitGatewayVPC'),
                        'mc': rec['tgw'].get('mcast'),
                        'types': sorted(k.replace('TransitGateway', '') for k in h)})
        v = rec['vpn']
        if v:
            vpn.append({'r': code, 'std': v.get('VPN Standard (1.25 Gbps)'), 'large': v.get('VPN Large (5 Gbps)'),
                        'conc': v.get('VPN Concentrator'), 'site': v.get('VPN Concentrator Sites'),
                        'cvEp': rec['cvpn'].get('endpoint'), 'cvConn': rec['cvpn'].get('conn')})
            unknown = set(v) - {'VPN Standard (1.25 Gbps)', 'VPN Large (5 Gbps)', 'VPN Concentrator', 'VPN Concentrator Sites'}
            if unknown:
                notes.append('VPN %s: unmapped vpnType %s' % (code, sorted(unknown)))
        if rec['pl']:
            pl.append(dict(r=code, **rec['pl']))
        if rec['ipv4']:
            ipv4.append({'r': code, 'inuse': rec['ipv4'].get('inuse'), 'idle': rec['ipv4'].get('idle')})
    return names, tgw, vpn, pl, ipv4, notes


# ---------------------------------------------------------------- Cloud WAN
def build_cloudwan(files, names):
    rows = []
    for code, path in files.items():
        doc = load(path)
        r = {}
        for sku, fam, a in products(doc):
            if a.get('locationType') != 'AWS Region':
                continue
            names.setdefault(code, a.get('location'))
            u, op = a['usagetype'], a.get('operation')
            key = {('CloudWAN-Attachment-Hours', 'CloudWANVPC'): 'vpc',
                   ('CloudWAN-Attachment-Hours', 'CloudWANConnect'): 'connect',
                   ('CloudWAN-Attachment-Hours', 'CloudWANS2SVPN'): 'vpn',
                   ('CloudWAN-Peering-Hours', 'CloudWANTGWPeering'): 'peer',
                   ('CloudWAN-CoreNetworkEdge-Hours', 'CloudWANCoreNetworkEdge'): 'cne',
                   ('CloudWAN-Bytes', 'CloudWANVPC'): 'gb',
                   ('CloudWAN-Bytes', 'CloudWANS2SVPN'): 'gbVpn',
                   ('CloudWAN-Attachment-Hours', 'CloudWANDirectConnect'): 'dx',
                   ('CloudWAN-Bytes', 'CloudWANDirectConnect'): 'gbDx'}.get((u.split('-', 1)[1], op))
            if key:
                r[key] = one(doc, sku)
            else:
                r.setdefault('_other', []).append(u + ':' + op)
        if r:
            rows.append(dict(r=code, **r))
    return rows


# ---------------------------------------------------------------- Data transfer (EC2)
def build_dt(files, names):
    inter, regional, xaz, internet = collections.defaultdict(dict), {}, {}, {}
    for code, path in files.items():
        doc = load(path)
        for sku, fam, a in products(doc):
            t = a.get('transferType')
            if a.get('fromRegionCode') != code:
                continue
            names.setdefault(code, a.get('fromLocation'))
            if t == 'InterRegion Outbound' and a.get('toLocationType') == 'AWS Region':
                to = a.get('toRegionCode')
                if REGION_RE.match(to or '') and not to.startswith(EXCLUDED_PREFIXES):
                    inter[code][to] = one(doc, sku)
            elif t == 'IntraRegion' and a['usagetype'].endswith('DataTransfer-Regional-Bytes'):
                regional[code] = one(doc, sku)
            elif t == 'IntraRegion-xAZ-Out':
                xaz[code] = one(doc, sku)
            elif t == 'AWS Outbound' and a.get('toLocation') == 'External':
                internet[code] = tiers(doc, sku)
    return inter, regional, xaz, internet


# ---------------------------------------------------------------- Direct Connect
# Destination location groups as used on https://aws.amazon.com/directconnect/pricing/ (column codes).
DX_GROUPS = [
    ('US', 'US', 'United States (excl. Hawaii)'),
    ('HI', 'HI', 'Hawaii'),
    ('CA', 'CA', 'Canada'),
    ('EU', 'EU', 'Europe'),
    ('JP', 'JP', 'Japan'),
    ('AP1', 'AP1', 'Hong Kong, Malaysia, Korea, Singapore, Taiwan, Thailand'),
    ('ID', 'ID', 'Indonesia'),
    ('PH', 'PH', 'Philippines'),
    ('IN', 'IN', 'India'),
    ('VN', 'VN', 'Vietnam'),
    ('SAMX', 'SA/MX', 'South America, Mexico'),
    ('AUNZ', 'AU/NZ', 'Australia, New Zealand'),
    ('ME', 'ME', 'Middle East, Israel, Türkiye'),
    ('AF', 'AF', 'Africa'),
]
DX_SEED = {
    'United States': 'US', 'Canada': 'CA', 'Japan': 'JP', 'Indonesia': 'ID', 'Philippines': 'PH', 'India': 'IN',
    'Vietnam': 'VN', 'Hong Kong': 'AP1', 'Malaysia': 'AP1', 'Korea': 'AP1', 'Singapore': 'AP1', 'Taiwan': 'AP1',
    'Thailand': 'AP1', 'Brazil': 'SAMX', 'Argentina': 'SAMX', 'Chile': 'SAMX', 'Colombia': 'SAMX', 'Peru': 'SAMX',
    'Mexico': 'SAMX', 'Australia': 'AUNZ', 'New Zealand': 'AUNZ', 'Bahrain': 'ME', 'Emirates': 'ME', 'Israel': 'ME',
    'Oman': 'ME', 'Istanbul': 'ME', 'South Africa': 'AF', 'Kenya': 'AF', 'Nigeria': 'AF',
}
EUROPE = {'Austria', 'Czechia', 'Denmark', 'Finland', 'France', 'Germany', 'Greece', 'Ireland', 'Italy', 'Netherlands',
          'Norway', 'Poland', 'Portugal', 'Spain', 'Sweden', 'Switzerland', 'United Kingdom'}
SITELINK_SEED = {'US': 'USA', 'HI': 'HAWAII', 'CA': 'CANADA', 'EU': 'EUROPE', 'JP': 'JAPAN', 'AP1': 'HKG-MNL-ICN-SIN-TPE',
                 'ID': 'SOUTH-ASIA', 'PH': 'PHILIPPINES', 'IN': 'INDIA', 'VN': 'SOUTH-ASIA', 'SAMX': 'SOUTH-AMERICA',
                 'AUNZ': 'AUSTRALIA', 'ME': 'ME', 'AF': 'AFRICA'}
SITELINK_ORDER = ['USA', 'HAWAII', 'CANADA', 'EUROPE', 'JAPAN', 'HKG-MNL-ICN-SIN-TPE', 'SOUTH-ASIA', 'PHILIPPINES',
                  'INDIA', 'AUSTRALIA', 'SOUTH-AMERICA', 'ME', 'AFRICA']


# Some DTO / SiteLink destinations have no port product (so no country attribute); seed them by name.
NAME_SEED = [
    (r', HI\b|Honolulu|Kapolei', 'HI'),
    (r'Melbourne|Sydney|\bSY\d|Brisbane|Perth|Canberra|Auckland|, AUS\b|, NZL\b', 'AUNZ'),
    (r'Inzai|Tokyo|Osaka|\bTY\d|, JPN\b', 'JP'),
    (r', (AL|AZ|CA|CO|FL|GA|IL|MA|MN|MO|NJ|NY|OH|OR|PA|TX|VA|WA)\b|Seattle|San Jose|Phoenix|Portland|Columbus', 'US'),
    (r'Mumbai|Chennai|Delhi|Hyderabad|Kolkata|, IND\b', 'IN'),
    (r'Sao Paulo|Rio de Janeiro|Brasil|, BRA\b', 'SAMX'),
]


def seed_group(loc, country):
    for pat, g in NAME_SEED[:1]:
        if re.search(pat, loc):
            return g
    if country in EUROPE:
        return 'EU'
    if country in DX_SEED:
        return DX_SEED[country]
    for pat, g in NAME_SEED[1:]:
        if re.search(pat, loc):
            return g
    return None


def refine_groups(prices, seed, group_ids):
    """prices: loc -> {src: price}. Assign each location to the group whose per-source modal price
    it matches most often. Corrects Price List country attributes that are missing or wrong."""
    assign = dict(seed)
    changes = {}
    for _ in range(3):
        modal = {}
        for g in group_ids:
            members = [l for l, gg in assign.items() if gg == g]
            srcs = {s for l in members for s in prices[l]}
            modal[g] = {s: mode([prices[l][s] for l in members if s in prices[l]]) for s in srcs}
        moved = False
        for l, pv in prices.items():
            def score(g):
                return sum(1 for s, v in pv.items() if modal[g].get(s) == v)
            best = max(group_ids, key=lambda g: (score(g), g == assign.get(l)))
            cur = assign.get(l)
            tied = [g for g in group_ids if score(g) == score(best)]
            if cur is None and len(tied) > 1:
                continue                      # ambiguous and no seed: leave out of the group statistics
            if cur is None or score(best) > score(cur):
                assign[l] = best
                changes[l] = (seed.get(l), best)
                moved = True
        if not moved:
            break
    return assign, changes


def build_dx(files, region_codes):
    loc_country, ports, dto, sitelink, vif_hour = {}, collections.defaultdict(lambda: collections.defaultdict(set)), \
        collections.defaultdict(dict), collections.defaultdict(dict), set()
    vif_mismatch = 0
    flat = collections.defaultdict(lambda: collections.defaultdict(set))
    dto_pub = {}
    for code, path in files.items():
        doc = load(path)
        for sku, fam, a in products(doc):
            u = a.get('usagetype', '')
            if fam in ('Direct Connect', None) and 'PortUsage' in u and a.get('country'):
                loc_country[a['directConnectLocation']] = a['country']
                jp = 'jp' if a['country'] == 'Japan' else 'other'
                speed = u.split(':')[-1]
                if 'FlatRatePortUsage' in u:
                    flat[speed][jp].add(one(doc, sku))
                else:
                    k = ('hosted' if 'HCPortUsage' in u else 'dedicated', speed)
                    ports[k][jp].add(one(doc, sku))
                    ports[k]['locs'].add(a['directConnectLocation'])
            elif fam == 'Direct Connect' and u.endswith('SiteLinkVifHour'):
                vif_hour.add(one(doc, sku))
            elif a.get('transferType') == 'SiteLink Data Transfer':
                sitelink[a['toLocation']][a['sitelinkOriginPopGroup']] = one(doc, sku)
            elif (fam == 'Data Transfer' and a.get('transferType', '').endswith('Outbound')
                  and a.get('fromRegionCode') in region_codes and a.get('toLocationType') == 'AWS Direct Connect Location'):
                p = one(doc, sku)
                key = (a['toLocation'], a['fromRegionCode'])
                if a.get('virtualInterfaceType') == 'Private':
                    dto[a['toLocation']][a['fromRegionCode']] = p
                elif a.get('virtualInterfaceType') == 'Public':
                    dto_pub[key] = p
    for (l, r), p in dto_pub.items():
        if l in dto and r in dto[l] and dto[l][r] != p:
            vif_mismatch += 1
        dto[l].setdefault(r, p)

    def speed_key(s):
        m = re.match(r'(\d+)([MG])', s)
        return (1 if m.group(2) == 'G' else 0, int(m.group(1))) if m else (9, 0)

    def table(kind):
        rows = []
        for (k, speed), d in sorted(ports.items(), key=lambda x: speed_key(x[0][1])):
            if k != kind:
                continue
            other = sorted(d.get('other', []))
            japan = sorted(d.get('jp', []))
            if not any(other + japan):
                continue                       # zero-priced placeholder SKUs (e.g. dedicated 100M)
            rows.append({'speed': speed, 'other': (other[0] if len(other) == 1 else other) if other else None,
                         'japan': (japan[0] if len(japan) == 1 else japan) if japan else None,
                         'locs': len(d['locs'])})
        return rows

    dedicated, hosted = table('dedicated'), table('hosted')
    flat_rows = []
    for speed, d in sorted(flat.items(), key=lambda x: (speed_key(x[0]), x[0])):
        m = re.match(r'(\d+G)(-Pair)?-(Tier\d)', speed)
        vals = sorted(d.get('other', set()) | d.get('jp', set()))
        if m:
            flat_rows.append({'speed': m.group(1), 'pair': bool(m.group(2)), 'tier': m.group(3),
                              'h': vals[0] if len(vals) == 1 else vals})

    # --- DTO: DX location -> page location group
    gids = [g[0] for g in DX_GROUPS]
    seed = {l: seed_group(l, loc_country.get(l)) for l in dto}
    seed = {l: g for l, g in seed.items() if g}
    assign, changes = refine_groups(dto, seed, gids)
    rows, mixed = [], []
    for r in region_codes:
        vals = []
        for g in gids:
            ps = [dto[l][r] for l, gg in assign.items() if gg == g and r in dto[l]]
            if not ps:
                vals.append(None)
                continue
            c = collections.Counter(ps)
            vals.append(c.most_common(1)[0][0])
            if len(c) > 1:
                mixed.append({'r': r, 'g': g, 'values': dict((str(k), v) for k, v in c.items())})
        if any(v is not None for v in vals):
            rows.append({'r': r, 'v': vals})
    members = collections.defaultdict(list)
    for l, g in assign.items():
        members[g].append(l)

    # --- SiteLink: destination location -> SiteLink pop group
    sl_seed = {l: SITELINK_SEED.get(seed_group(l, loc_country.get(l))) for l in sitelink}
    sl_seed = {l: g for l, g in sl_seed.items() if g}
    srcs = [g for g in SITELINK_ORDER if any(g in v for v in sitelink.values())]
    srcs += sorted({s for v in sitelink.values() for s in v} - set(srcs))
    sl_assign, sl_changes = refine_groups(sitelink, sl_seed, srcs)
    dsts = [g for g in srcs if any(gg == g for gg in sl_assign.values())]
    sl_rows, sl_mixed = [], []
    for s in srcs:
        vals = []
        for g in dsts:
            ps = [sitelink[l][s] for l, gg in sl_assign.items() if gg == g and s in sitelink[l]]
            c = collections.Counter(ps)
            vals.append(c.most_common(1)[0][0] if c else None)
            if len(c) > 1:
                sl_mixed.append({'from': s, 'to': g, 'values': dict((str(k), v) for k, v in c.items())})
        sl_rows.append({'from': s, 'v': vals})

    return {
        'dedicated': dedicated, 'hosted': hosted, 'flatRate': flat_rows,
        'dto': {'groups': [{'id': g[0], 'label': g[1], 'desc': g[2], 'members': sorted(members[g[0]])} for g in DX_GROUPS],
                'rows': rows, 'mixed': mixed, 'publicPrivateMismatch': vif_mismatch,
                'reassigned': {l: list(v) for l, v in sorted(changes.items())},
                'unassigned': sorted(set(dto) - set(assign))},
        'sitelink': {'vifHour': sorted(vif_hour), 'groups': srcs, 'dst': dsts, 'rows': sl_rows, 'mixed': sl_mixed,
                     'members': {g: sorted(l for l, gg in sl_assign.items() if gg == g) for g in dsts},
                     'reassigned': {l: list(v) for l, v in sorted(sl_changes.items())},
                     'unassigned': sorted(set(sitelink) - set(sl_assign))},
        'locations': len(loc_country),
    }


# ---------------------------------------------------------------- Global Accelerator
GA_GROUPS = [
    ('NA', 'North America', 'US, Mexico, Canada'),
    ('EU', 'Europe', 'Europe, Israel, Türkiye'),
    ('AP', 'Asia Pacific', 'Asia Pacific (excl. India, Philippines, Thailand, Vietnam, South Korea, Australia/NZ)'),
    ('KR', 'South Korea', 'South Korea'),
    ('IN', 'India', 'India, Philippines, Thailand, Vietnam'),
    ('AU', 'Australia', 'Australia, New Zealand'),
    ('ME', 'Middle East', 'Middle East'),
    ('SA', 'South America', 'South America'),
    ('ZA', 'South Africa', 'South Africa, Kenya, Nigeria'),
]


def build_ga(path):
    doc = load(path)
    fixed, cells, check = None, {}, collections.defaultdict(set)
    for sku, fam, a in products(doc):
        if a.get('usagetype') == 'Global-Accelerator-fixed-fee':
            fixed = one(doc, sku)
            continue
        if 'fromLocation' not in a or a.get('dominantnon-dominant') != 'Dominant':
            continue
        p = one(doc, sku)
        k = (a['fromLocation'], a['toLocation'])
        check[k].add((a.get('trafficDirection'), a.get('clientLocation'), p))
        if a.get('trafficDirection') == 'Out' and a.get('clientLocation') == 'Internet':
            cells[k] = p
    ids = [g[0] for g in GA_GROUPS]
    extra = sorted({k[0] for k in cells} - set(ids))
    ids += extra
    rows = [{'from': f, 'v': [cells.get((f, t)) for t in ids]} for f in ids if any((f, t) in cells for t in ids)]
    differs = sorted('%s-%s' % k for k, s in check.items() if len({x[2] for x in s}) > 1)
    return {'fixed': fixed, 'groups': [{'id': g[0], 'label': g[1], 'desc': g[2]} for g in GA_GROUPS] +
            [{'id': e, 'label': e, 'desc': e} for e in extra], 'rows': rows, 'directionOrClientDiffers': differs}


# ---------------------------------------------------------------- Elastic Load Balancing
ELB_KIND = {'LoadBalancing:Application': 'alb', 'LoadBalancing:Network': 'nlb', 'LoadBalancing:Gateway': 'gwlb',
            'LoadBalancing': 'clb'}


def build_elb(files, names):
    """Per Region: hour / LCU-hour / reserved LCU-hour per LB type, ALB trust store hour, CLB GB.
    Outposts SKUs (locationType 'AWS Outposts' or usagetype '*-Outposts-*') are left out."""
    rows, other = [], set()
    for code, path in files.items():
        doc = load(path)
        r = {}
        for sku, fam, a in products(doc):
            if a.get('locationType') != 'AWS Region':
                continue
            names.setdefault(code, a.get('location'))
            u, kind = a.get('usagetype', ''), ELB_KIND.get(a.get('operation'))
            if 'Outposts' in u or not kind:
                other.add(u.split('-', 1)[-1] + ':' + str(a.get('operation')))
                continue
            # us-east-1 usage types carry no Region prefix, so match on the suffix
            if u.endswith('TS-LoadBalancerUsage'):
                key = 'ts'
            elif u.endswith('LoadBalancerUsage'):
                key = 'h'
            elif u.endswith('ReservedLCUUsage'):
                key = 'res'
            elif u.endswith('LCUUsage'):
                key = 'lcu'
            elif u.endswith('IdleProvisionedLBCapacity'):
                key = 'idle'
            elif u.endswith('DataProcessing-Bytes') or u == 'DataProcessing-Bytes':
                key = 'gb'
            else:
                other.add(u + ':' + a.get('operation'))
                continue
            r[kind + '_' + key] = one(doc, sku)
        if r:
            rows.append(dict(r=code, **r))
    return rows, sorted(other)


# ---------------------------------------------------------------- VPC Lattice (inside AmazonVPC)
def build_lattice(files):
    rows = []
    free = {}
    for code, path in files.items():
        doc = load(path)
        r = {}
        for sku, fam, a in products(doc):
            if a.get('locationType') != 'AWS Region':
                continue
            u = a.get('usagetype', '')
            k = u.split('-', 1)[1] if re.match(r'^[A-Z]{2,4}\d*-', u) else u
            key = {'VPCLattice-Service-Hourly': 'svc', 'VPCLattice-DataProcessing-Bytes': 'gb',
                   'VPCLattice-RequestCount-Charged': 'req', 'VPCLattice-ConnectionCount-Charged': 'conn',
                   'VpcLattice-Service-Network-Resource-Hours': 'res',
                   'VpcLattice-Service-Network-ODB-Resource-Hours': 'resOdb',
                   'VpcResource-Provider-Bytes': 'provGb'}.get(k)
            if key in ('req', 'conn'):
                dims = ondemand(doc, sku)          # $/request is ~1e-7: keep it as $ per million
                r[key + 'M'] = round(dims[0]['usd'] * 1e6, 6) if dims else None
            elif key:
                r[key] = one(doc, sku)
            elif k == 'VpcResource-Consumer-Bytes':
                r['resGb'] = tiers(doc, sku)
            elif k in ('VPCLattice-RequestCount-Free', 'VPCLattice-ConnectionCount-Free'):
                m = re.search(r'first ([\d,]+)', a.get('groupDescription', ''))
                if m:
                    free['req' if 'Request' in k else 'conn'] = int(m.group(1).replace(',', ''))
        if any(x in r for x in ('svc', 'res', 'resOdb')):
            rows.append(dict(r=code, **r))
    return rows, free


# ---------------------------------------------------------------- shared helpers for the newer offers
def prefix_of(doc):
    """Most common usage type prefix of a region file (e.g. APN2, USE1, EU, Global)."""
    c = collections.Counter(p['attributes'].get('usagetype', '').split('-', 1)[0]
                            for p in doc['products'].values() if '-' in p['attributes'].get('usagetype', ''))
    return c.most_common(1)[0][0] if c else ''


def ukey(u, pfx):
    for p in (pfx, 'Global'):
        if p and u.startswith(p + '-'):
            return u[len(p) + 1:]
    return u


def tiers_x(doc, sku, mult=1):
    """Tiers with the unit price scaled (e.g. x1e6 for $ per million requests)."""
    return [[d['begin'], d['end'], round(d['usd'] * mult, 6)] for d in ondemand(doc, sku)]


def one_x(doc, sku, mult):
    dims = ondemand(doc, sku)
    return round(dims[0]['usd'] * mult, 6) if dims else None


def paid(tl):
    """First non-zero unit price of a tier list (skips free tiers)."""
    for t in tl or []:
        if t[2]:
            return t[2]
    return None


# ---------------------------------------------------------------- API Gateway
def build_apigw(files):
    rows, sizes = [], set()
    for code, path in files.items():
        doc = load(path)
        pfx, r, cache = prefix_of(doc), {}, {}
        for sku, fam, a in products(doc):
            k = ukey(a.get('usagetype', ''), pfx)
            if k == 'ApiGatewayRequest':
                r['rest'] = tiers_x(doc, sku, 1e6)
            elif k == 'ApiGatewayHttpRequest':
                r['http'] = tiers_x(doc, sku, 1e6)
            elif k == 'ApiGatewayMessage':
                r['wsMsg'] = tiers_x(doc, sku, 1e6)
            elif k == 'ApiGatewayMinute':
                r['wsMin'] = one_x(doc, sku, 1e6)
            elif k.startswith('ApiGatewayCacheUsage:'):
                cache[a['cacheMemorySizeGb']] = one(doc, sku)
                sizes.add(a['cacheMemorySizeGb'])
            elif k == 'APIGateway-Portal-Months':
                r['portal'] = one(doc, sku)
            elif k == 'APIGateway-Portal-Product-Months':
                r['portalProduct'] = one(doc, sku)
        if r:
            r['cache'] = cache
            rows.append(dict(r=code, **r))
    order = sorted(sizes, key=float)
    for x in rows:
        x['cache'] = [x['cache'].get(s) for s in order]
    return {'rows': rows, 'cacheSizes': order}


# ---------------------------------------------------------------- CloudFront (+ flat-rate plans)
CF_EDGE = {'United States': 'US', 'Canada': 'CA', 'Europe': 'EU', 'Japan': 'JP', 'Asia Pacific': 'AP',
           'Australia': 'AU', 'India': 'IN', 'South America': 'SA', 'South Africa': 'ZA', 'Middle East': 'ME'}
CF_ORDER = ['US', 'CA', 'EU', 'ZA', 'ME', 'SA', 'JP', 'AU', 'AP', 'IN']


def build_cloudfront(files, plans_path):
    edge = collections.defaultdict(dict)
    shield_rows, misc, free = [], {}, {}
    for code, path in files.items():
        doc = load(path)
        for sku, fam, a in products(doc):
            u = a.get('usagetype', '')
            if code == 'aws-other':
                loc = a.get('fromLocation') if a.get('transferType') else a.get('location')
                g = CF_EDGE.get(loc)
                t = a.get('transferType')
                if g and t == 'CloudFront Outbound':
                    edge[g]['dto'] = tiers(doc, sku)
                elif g and t == 'CloudFront to Origin':
                    edge[g]['origin'] = one(doc, sku)
                elif g and a.get('requestType') == 'CloudFront-Request-Tier1':
                    edge[g]['http'] = one_x(doc, sku, 1e4)
                elif g and a.get('requestType') == 'CloudFront-Request-Tier2':
                    edge[g]['https'] = one_x(doc, sku, 1e4)
                elif g and u.endswith('Requests-HTTPS-Proxy-FLE'):
                    edge[g]['fle'] = one_x(doc, sku, 1e4)
                elif u == 'Global-DataTransfer-Out-Bytes':
                    free['dtoGb'] = (tiers(doc, sku) or [[0, None, 0]])[0][1]
                elif u == 'Global-Requests-Tier1':
                    free['req'] = (tiers(doc, sku) or [[0, None, 0]])[0][1]
                elif u == 'Executions-CloudFrontFunctions':
                    misc['fnM'] = round(paid(tiers_x(doc, sku, 1e6)) or 0, 6)
                    free['fn'] = tiers(doc, sku)[0][1]
                elif u == 'KeyValueStore-EdgeReads':
                    misc['kvsReadM'] = round(paid(tiers_x(doc, sku, 1e6)) or 0, 6)
                    free['kvs'] = tiers(doc, sku)[0][1]
                elif u == 'KeyValueStore-APIOperations':
                    misc['kvsApi'] = one(doc, sku)
                elif u == 'Invalidations':
                    misc['inval'] = paid(tiers(doc, sku))
                    free['inval'] = tiers(doc, sku)[0][1]
                elif u == 'RealTimeLog-KinesisDataStream':
                    misc['rtlogM'] = one_x(doc, sku, 1e6)
                elif u == 'StaticIP-IPv4':
                    misc['staticV4'] = one(doc, sku)
                elif u == 'StaticIP-IPv6':
                    misc['staticV6'] = one(doc, sku)
                elif u.endswith('SSL-Cert-Custom'):
                    misc['cert'] = one(doc, sku)
            if a.get('requestType') == 'CloudFront-Request-Origin-Shield' and a.get('locationType') == 'AWS Region':
                shield_rows.append({'r': code, 'req': one_x(doc, sku, 1e4)})
            elif u.endswith('Lambda-Edge-Request'):
                misc['lambdaReqM'] = one_x(doc, sku, 1e6)
            elif u.endswith('Lambda-Edge-GB-Second'):
                misc['lambdaGbS'] = one(doc, sku)
    groups = [g for g in CF_ORDER if g in edge] + sorted(set(edge) - set(CF_ORDER))
    inv = {v: k for k, v in CF_EDGE.items()}
    t0 = next((edge[g]['dto'] for g in groups if edge[g].get('dto')), [])
    out = {'groups': [{'id': g, 'loc': inv.get(g, g)} for g in groups],
           'dtoTiers': [[t[0], t[1]] for t in t0],
           'edge': [dict(id=g, **edge[g]) for g in groups],
           'originShield': shield_rows, 'misc': misc, 'free': free, 'plans': build_cf_plans(plans_path)}
    return out


def build_cf_plans(path):
    if not path:
        return []
    doc = load(path)
    plans = []
    for lst in doc['terms'].get('FlatRate', {}).values():
        for p in lst:
            q = {f['featureCode']: float(f['usageQuota']['value']) for f in p.get('features', [])}
            plans.append({'code': p['planCode'], 'usd': float(p['subscriptionPrice']['pricePerUnit']['USD']),
                          'req': q.get('Requests'), 'gb': q.get('DataTransfer'), 's3Gb': q.get('S3Storage'),
                          'overage': sorted({f.get('overagePolicy') for f in p.get('features', [])} - {None})})
    plans.sort(key=lambda x: (x['usd'], x['code']))
    return plans


# ---------------------------------------------------------------- Interconnect (multicloud / last mile)
def build_interconnect(files):
    price = collections.defaultdict(lambda: collections.defaultdict(set))   # kind -> (bw,tier) -> {usd}
    homes = collections.defaultdict(set)                                     # kind/provider -> home regions
    pairs = collections.defaultdict(dict)                                    # region -> {"GCP|us-east-1": tier}
    metros = collections.defaultdict(dict)                                   # region -> {"NYC": tier}
    partner_regions, dto = {}, set()
    for code, path in files.items():
        doc = load(path)
        for sku, fam, a in products(doc):
            u = a.get('usagetype', '')
            if 'MgdConUsage' in u:
                kind = 'mc' if a.get('partnerCloudServiceProvider') else 'lm'
                who = a.get('partnerCloudServiceProvider') or a.get('partnerMetro')
                price[kind][(a['interconnectBandwidth'], a['interconnectTier'])].add(one(doc, sku))
                homes[who].add(code)
            elif 'DataXfer' in u:
                dto.add(one(doc, sku))
                if a.get('trafficDirection') != 'Out':
                    continue
                if a.get('partnerCloudServiceProvider'):
                    k = a['partnerCloudServiceProvider'] + '|' + a['toregionname']
                    partner_regions[k] = a.get('interconnectRegionName')
                    pairs[code][k] = a['interconnectTier']
                elif a.get('partnerMetro'):
                    metros[code][a['partnerMetro']] = a['interconnectTier']

    def bw_key(s):
        m = re.match(r'(\d+)([MG])', s)
        return (1 if m.group(2) == 'G' else 0, int(m.group(1)))

    def table(kind):
        bws = sorted({k[0] for k in price[kind]}, key=bw_key)
        tl = sorted({k[1] for k in price[kind]})
        rows, odd = [], []
        for b in bws:
            vals = []
            for t in tl:
                s = price[kind].get((b, t))
                if not s:
                    vals.append(None)
                    continue
                nz = sorted(x for x in s if x)
                vals.append(nz[-1] if nz else 0.0)
                if len(s) > 1:
                    odd.append('%s %s: %s' % (b, t, sorted(s)))
            rows.append({'bw': b, 'v': vals})
        return {'tiers': tl, 'rows': rows, 'differs': odd}

    prov_order = sorted(partner_regions, key=lambda k: (k.split('|')[0], k.split('|')[1]))
    return {'mc': dict(table('mc'), partners=[{'k': k, 'name': partner_regions[k]} for k in prov_order],
                       pairs=[{'r': r, 't': [pairs[r].get(k) for k in prov_order]} for r in pairs]),
            'lm': dict(table('lm'), metros=sorted({m for v in metros.values() for m in v}),
                       pairs=[{'r': r, 't': metros[r]} for r in metros]),
            'homes': {k: sorted(v) for k, v in homes.items()}, 'dtoValues': sorted(dto)}


# ---------------------------------------------------------------- Route 53
R53_Q = [('DNS-Queries', 'std'), ('LBR-Queries', 'lbr'), ('Geo-Queries', 'geo'), ('Geo-Proximity-Queries', 'geoprox'),
         ('Cidr-Queries', 'ip')]


def build_route53(files):
    g, rows = {}, []
    for code, path in files.items():
        doc = load(path)
        pfx, r = prefix_of(doc), {}
        for sku, fam, a in products(doc):
            u = a.get('usagetype', '')
            if code == 'aws-other':
                k = ukey(u, 'Global')
                if k == 'HostedZone':
                    g['zone'] = tiers(doc, sku)
                elif k == 'RRSets':
                    g['records'] = one(doc, sku)
                elif k == 'Cidr-Blocks':
                    g['cidr'] = tiers(doc, sku)
                elif k == 'Traffic-Flow-Policy-Records':
                    g['flow'] = one(doc, sku)
                elif k.startswith('Health-Check-'):
                    g[{'Health-Check-AWS': 'hcAws', 'Health-Check-Non-AWS': 'hcExt', 'Health-Check-Option-AWS': 'hcOptAws',
                       'Health-Check-Option-Non-AWS': 'hcOptExt'}[k]] = tiers(doc, sku)
                elif k.startswith('GlobalResolver-'):
                    key = k.replace('GlobalResolver-', '')
                    g.setdefault('gr', {})[key] = tiers_x(doc, sku, 1e6) if key == 'Queries' else one(doc, sku)
                else:
                    for uk, q in R53_Q:
                        if k == uk:
                            g.setdefault('q', {})[q] = tiers_x(doc, sku, 1e6)
                        elif k == 'Intra-AWS-' + uk:
                            g.setdefault('qAlias', {})[q] = one(doc, sku)
                continue
            k = ukey(u, pfx)
            key = {'ResolverNetworkInterface': 'eni', 'ResolverNetworkInterface-SecurityEnabled': 'eniDoh',
                   'DNS-FirewallDomainName': 'fwDomain', 'AdvancedDNS-ThreatProtectionsVPCAssociationHours': 'fwAdv',
                   'DNS-ProfileBasePackage': 'profBase', 'DNS-ProfileAssociationCount': 'profAssoc',
                   'Resolver:Outpost-Hours': 'outpost'}.get(k)
            if key:
                r[key] = one(doc, sku)
            elif k == 'DNS-Queries':
                r['q'] = tiers_x(doc, sku, 1e6)
            elif k == 'DNS-FirewallQueries':
                r['fwQ'] = tiers_x(doc, sku, 1e6)
        if r:
            rows.append(dict(r=code, **r))
    return {'global': g, 'rows': rows}


# ---------------------------------------------------------------- Network Firewall
def build_nfw(files):
    rows = []
    for code, path in files.items():
        doc = load(path)
        pfx, r = prefix_of(doc), {}
        for sku, fam, a in products(doc):
            k = ukey(a.get('usagetype', ''), pfx)
            key = {'Endpoint-Hour': 'ep', 'Traffic-GB-Processed': 'gb', 'Secondary-Endpoint-Hour': 'sec',
                   'Advanced-Inspection-Endpoint-Hour': 'adv', 'Advanced-Inspection-Traffic-GB-Processed': 'advGb',
                   'Advanced-Threat-Protection-Traffic-GB-Processed': 'atp',
                   'Traffic-Bytes-Processed-Transit-Gateway': 'tgwGb'}.get(k)
            if key:
                r[key] = one(doc, sku)
        if r:
            rows.append(dict(r=code, **r))
    return rows


# ---------------------------------------------------------------- WAF
WAF_ONE = {'WebACLV2': 'acl', 'RuleV2': 'rule', 'AMR-BotControl': 'bot', 'AMR-ATP': 'fraud', 'AMR-AntiDDoS': 'ddos'}
WAF_M = {'RequestV2-Tier0': 'req', 'AMR-AntiDDoS-Request': 'ddosReq', 'ChallengeServed': 'challenge',
         'RequestV2-32KB': 'b32', 'RequestV2-48KB': 'b48', 'RequestV2-64KB': 'b64'}
WAF_T = {'AMR-BotControl-Request': 'botReq', 'AMR-BotControl-Targeted-Request': 'botTReq',
         'AMR-FraudControl-Request': 'fraudReq'}


def build_waf(files):
    rows, glob_row = [], None
    for code, path in files.items():
        doc = load(path)
        pfx, r = prefix_of(doc), {'wcu': {}}
        for sku, fam, a in products(doc):
            k = ukey(a.get('usagetype', ''), pfx)
            if code == 'aws-other' and not a.get('usagetype', '').startswith('Global-'):
                continue                      # legacy WAF Classic (global) SKUs
            if k in WAF_ONE:
                r[WAF_ONE[k]] = one(doc, sku)
            elif k in WAF_M:
                r[WAF_M[k]] = one_x(doc, sku, 1e6)
            elif k in WAF_T:
                r[WAF_T[k]] = tiers_x(doc, sku, 1e6)
            elif k == 'CaptchaAttempted':
                r['captcha'] = one_x(doc, sku, 1e4)
            elif re.match(r'RequestV2-Tier\d-(\d+)WCU$', k):
                r['wcu'][re.match(r'RequestV2-Tier\d-(\d+)WCU$', k).group(1)] = one_x(doc, sku, 1e6)
            elif k == 'ShieldProtected-Capped-RequestV2-Count':
                r['shieldFreeReq'] = (tiers(doc, sku) or [[0, None, 0]])[0][1]
        if len(r) > 1:
            if code == 'aws-other':
                glob_row = r
            else:
                rows.append(dict(r=code, **r))
    return {'global': glob_row, 'rows': rows}


# ---------------------------------------------------------------- Shield
def build_shield(files):
    g, rows = {}, []
    for code, path in files.items():
        doc = load(path)
        r = {}
        for sku, fam, a in products(doc):
            u = a.get('usagetype', '')
            if u == 'Shield-Monthly-Fee':
                g['monthly'] = ondemand(doc, sku)[0]['usd'] if ondemand(doc, sku) else None
            elif u == 'Global-DataTransfer-Shield-Bytes':
                g[{'CloudFront': 'cf', 'GlobalAccelerator': 'ga'}.get(a.get('resourceType'), a.get('resourceType'))] = tiers(doc, sku)
            elif u.endswith('DataTransfer-Shield-Bytes') and a.get('fromRegionCode') == code:
                r[{'LoadBalancing': 'elb', 'ShieldProtectionEIP': 'eip'}.get(a.get('resourceType'), a.get('resourceType'))] = tiers(doc, sku)
        if r:
            rows.append(dict(r=code, **r))
    return {'global': g, 'rows': rows}


# ---------------------------------------------------------------- Firewall Manager
FMS_TYPES = [('Policy-WAF', 'WAFv2', 'waf'), ('Policy-WAF', 'WAF', 'wafClassic'), ('Policy-Shield', 'Shield', 'shield'),
             ('Policy-Security-Group', 'Common', 'sg'), ('Policy-Security-Group', 'Content-Audit', 'sgContent'),
             ('Policy-Security-Group', 'Usage-Audit', 'sgUsage'), ('Policy-Network-Acl-Common', 'Network-Acl-Common', 'nacl'),
             ('Policy-Network-Firewall', 'Network-Firewall', 'nfw'),
             ('Policy-Import-Network-Firewall', 'Import-Network-Firewall', 'nfwImport'),
             ('Policy-DNS-Firewall', 'DNS-Firewall', 'dnsfw'), ('Policy-PaloAlto', 'PaloAlto', 'paloalto'),
             ('Policy-Fortinet', 'Fortinet', 'fortinet')]


def build_fms(files):
    rows, glob_row = [], None
    for code, path in files.items():
        doc = load(path)
        pfx, r = ('Global' if code == 'aws-other' else prefix_of(doc)), {}
        for sku, fam, a in products(doc):
            k, op = ukey(a.get('usagetype', ''), pfx), a.get('operation', '')
            if code == 'aws-other' and k == 'Policy' and a.get('awsresource') == 'AmazonCloudFront':
                r['cloudfront'] = one(doc, sku)
            for uk, o, key in FMS_TYPES:
                if k == uk and op == o:
                    r[key] = one(doc, sku)
        if r:
            if code == 'aws-other':
                glob_row = r
            else:
                rows.append(dict(r=code, **r))
    return {'types': [t[2] for t in FMS_TYPES], 'global': glob_row, 'rows': rows}


# ---------------------------------------------------------------- VPC extras (AmazonVPC offer)
def build_vpc_extra(files):
    rows = []
    for code, path in files.items():
        doc = load(path)
        pfx, r = prefix_of(doc), {}
        for sku, fam, a in products(doc):
            if a.get('locationType') not in (None, 'AWS Region'):
                continue
            k = ukey(a.get('usagetype', ''), pfx)
            key = {'VPCEncryptionControls-hours': 'enc', 'ENI-Mirror': 'mirror', 'IPAddressManager-IP-Hours': 'ipam',
                   'PublicIPv4:ContiguousBlock': 'v4block', 'Analysis-Runs': 'ra', 'NetworkInterface-Assessment': 'naa',
                   'RouteServer-EndpointHours': 'rs'}.get(k)
            if key:
                r[key] = one(doc, sku)
        if r:
            rows.append(dict(r=code, **r))
    return rows


def fetch_page_json(cache, path, refresh):
    """JSON behind an official pricing page (gzip-encoded on the wire)."""
    import gzip
    local = os.path.join(cache, 'page', path.replace('/', '_') + '.json')
    url = '%s/%s/USD/current/%s.json' % (PAGE_BASE, path.split('/')[0], path.split('/')[1])
    if refresh or not os.path.exists(local):
        os.makedirs(os.path.dirname(local), exist_ok=True)
        req = urllib.request.Request(url, headers={'Accept-Encoding': 'gzip'})
        with urllib.request.urlopen(req, timeout=120) as r:
            b = r.read()
        if b[:2] == b'\x1f\x8b':
            b = gzip.decompress(b)
        with open(local, 'wb') as f:
            f.write(b)
    return load(local), url


def build_nat(cache, refresh, names):
    d, url = fetch_page_json(cache, 'ec2/natgateway', refresh)
    def norm(n):
        return re.sub(r'^EU \(', 'Europe (', n or '')
    by_name = {norm(v): k for k, v in names.items()}
    keys = {'Hourly charge for NAT Gateways': 'h', 'Charge for per GB data processed by NatGateways': 'gb',
            'g03zZA9QDqyDCHNtHqaCJlNdgpbSIHIuGsuW2ty2QrY': 'rh', 'yl8H9iVT1u9HhTJORoUA1t4vWdL_N7bGgcdBDCSbBTI': 'rgb',
            'Per hour and per Gbps charge for NAT Gateways with provisioned bandwidth': 'pbw',
            'Charge for per GB data processed by NAT Gateways with provisioned bandwidth': 'pbwGb'}
    rows, unmatched = [], []
    for name, v in d['regions'].items():
        code = by_name.get(norm(name))
        if not code:
            unmatched.append(name)
            continue
        r = {keys[k]: round(float(x['price']), 6) for k, x in v.items() if k in keys}
        if r:
            rows.append(dict(r=code, **r))
    meta = {'publicationDate': d['manifest'].get('hawkFilePublicationDate'), 'source': url, 'kind': 'page',
            'page': 'https://aws.amazon.com/vpc/pricing/'}
    return rows, meta, sorted(unmatched)


# ---------------------------------------------------------------- CloudWatch (vended logs / flow monitor / metrics)
def build_cloudwatch(files):
    rows, g = [], {}
    for code, path in files.items():
        doc = load(path)
        pfx, r = prefix_of(doc), {}
        for sku, fam, a in products(doc):
            u = a.get('usagetype', '')
            if code == 'aws-other' or u.startswith('Global-'):
                k = ukey(u, 'Global')
                if k == 'CW:NFM-ResourceHours':
                    g['nfmFreeHours'] = (tiers(doc, sku) or [[0, None, 0]])[0][1]
                elif k == 'CW:MetricMonitorUsage':
                    g['metricFree'] = (tiers(doc, sku) or [[0, None, 0]])[0][1]
                continue
            k = ukey(u, pfx)
            if k == 'VendedLog-Bytes':
                r['cw'] = tiers(doc, sku)
            elif k == 'VendedLogIA-Bytes':
                r['ia'] = tiers(doc, sku)
            elif k == 'S3-Egress-Bytes':
                r['s3'] = tiers(doc, sku)
            elif k == 'FH-Egress-Bytes':
                r['fh'] = tiers(doc, sku)
            elif k == 'S3-Egress-InputBytes':
                r['parquet'] = one(doc, sku)
            elif k == 'CW:NFM-ResourceHours':
                r['nfm'] = one(doc, sku)
            elif k == 'CWNMHybrid-Paid':
                r['nm'] = one(doc, sku)
            elif k == 'CW:MetricMonitorUsage':
                r['metric'] = tiers(doc, sku)
        if r:
            rows.append(dict(r=code, **r))
    return {'global': g, 'rows': rows}


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', default=os.environ.get('PRICE_CACHE', DEFAULT_CACHE))
    ap.add_argument('--refresh', action='store_true', help='re-download even if cached')
    ap.add_argument('--out', default=os.path.join(REPO, 'pricing', 'data.json'))
    args = ap.parse_args()

    idx, meta, files, excluded = offer_files(args.cache, args.refresh)
    names, tgw, vpn, pl, ipv4, notes = build_vpc(files['AmazonVPC'])
    cw = build_cloudwan(files['AWSCloudWAN'], names)
    inter, regional, xaz, internet = build_dt(files['AWSDataTransfer'], names)
    all_codes = set(names) | set(inter)
    regions = region_list({c: 1 for c in all_codes}, names)
    order = [r['code'] for r in regions]
    pos = {c: i for i, c in enumerate(order)}

    def by_order(rows):
        return sorted([x for x in rows if x['r'] in pos], key=lambda x: pos[x['r']])

    dx = build_dx(files['AWSDirectConnect'], order)
    ga = build_ga(files['AWSGlobalAccelerator']['aws-other'])
    elb, elb_other = build_elb(files['AWSELB'], names)
    lattice, lattice_free = build_lattice(files['AmazonVPC'])
    apigw = build_apigw(files['AmazonApiGateway'])
    cf = build_cloudfront(files['AmazonCloudFront'], files['CloudFrontPlans'].get('aws-other'))
    ic = build_interconnect(files['AWSInterconnect'])
    r53 = build_route53(files['AmazonRoute53'])
    nfw = build_nfw(files['AWSNetworkFirewall'])
    waf = build_waf(files['awswaf'])
    shield = build_shield(files['AWSShield'])
    fms = build_fms(files['AWSFMS'])
    vpcx = build_vpc_extra(files['AmazonVPC'])
    cwatch = build_cloudwatch(files['AmazonCloudWatch'])
    nat, nat_meta, nat_unmatched = build_nat(args.cache, args.refresh, names)
    meta['NATGatewayPage'] = nat_meta

    dt_regions = [c for c in order if c in inter]
    matrix = [[inter[f].get(t) if f != t else None for t in dt_regions] for f in dt_regions]

    data = {
        'generatedAt': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'indexPublicationDate': idx.get('publicationDate'),
        'hoursPerMonth': 730,
        'currency': 'USD',
        'sources': meta,
        'regions': regions,
        'excludedRegions': excluded,
        'dx': dx,
        'cloudwan': by_order(cw),
        'tgw': by_order(tgw),
        'dt': {'regions': dt_regions, 'matrix': matrix,
               'intra': [{'r': c, 'regional': regional.get(c), 'xaz': xaz.get(c)} for c in order if c in regional],
               'internet': [{'r': c, 't': internet[c]} for c in order if c in internet],
               'ipv4': by_order(ipv4)},
        'vpn': by_order(vpn),
        'ga': ga,
        'privatelink': by_order(pl),
        'elb': {'rows': by_order(elb), 'skipped': elb_other},
        'lattice': {'rows': by_order(lattice), 'freePerHour': lattice_free},
        'apigw': dict(apigw, rows=by_order(apigw['rows'])),
        'cloudfront': dict(cf, originShield=by_order(cf['originShield'])),
        'interconnect': {'mc': dict(ic['mc'], pairs=by_order(ic['mc']['pairs'])),
                         'lm': dict(ic['lm'], pairs=by_order(ic['lm']['pairs'])),
                         'homes': ic['homes'], 'dtoValues': ic['dtoValues']},
        'route53': dict(r53, rows=by_order(r53['rows'])),
        'nfw': by_order(nfw),
        'waf': dict(waf, rows=by_order(waf['rows'])),
        'shield': dict(shield, rows=by_order(shield['rows'])),
        'fms': dict(fms, rows=by_order(fms['rows'])),
        'vpc': {'nat': by_order(nat), 'extra': by_order(vpcx)},
        'cloudwatch': dict(cwatch, rows=by_order(cwatch['rows'])),
        'notes': notes,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    print('wrote %s (%d bytes); regions=%d dx-locations=%d' % (args.out, os.path.getsize(args.out), len(regions), dx['locations']))
    for k in ('reassigned', 'unassigned', 'mixed'):
        print('dx.dto.%s: %s' % (k, json.dumps(dx['dto'][k], ensure_ascii=False)[:1500]))
        print('dx.sitelink.%s: %s' % (k, json.dumps(dx['sitelink'][k], ensure_ascii=False)[:1500]))
    print('dx public/private DTO mismatches:', dx['dto']['publicPrivateMismatch'])
    print('ga direction/client differences:', ga['directionOrClientDiffers'][:20])
    print('notes:', notes[:20])
    print('elb regions=%d skipped usage types: %s' % (len(elb), elb_other))
    print('lattice regions=%d free/hour: %s' % (len(lattice), lattice_free))
    print('nat rows=%d unmatched page regions: %s' % (len(nat), nat_unmatched))
    print('interconnect price differences:', ic['mc']['differs'], ic['lm']['differs'], 'dto values', ic['dtoValues'])
    for k in ('apigw', 'cloudfront', 'route53', 'nfw', 'waf', 'shield', 'fms', 'vpc', 'cloudwatch'):
        v = data[k]
        n = len(v) if isinstance(v, list) else len(v.get('rows', v.get('nat', [])))
        print('%s rows=%d' % (k, n))
    other_cw = sorted({o for x in data['cloudwan'] for o in x.get('_other', [])})
    if other_cw:
        print('cloudwan unmapped usage types:', other_cw)
    return 0


if __name__ == '__main__':
    sys.exit(main())
