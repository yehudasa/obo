import sys
import socket
import os
import boto
import boto.s3.connection
import argparse
import json
import urllib
from boto.s3.key import Key

import xml.etree.cElementTree as et
from xmljson import yahoo as xj
from xml.etree.ElementTree import fromstring as xmlfromstring

class OBO:
    def __init__(self, access_key, secret_key, host):
        host, port = (host.rsplit(':', 1) + [None])[:2]
        if port:
            port = int(port)

        self.conn = boto.connect_s3(
                aws_access_key_id = access_key,
                aws_secret_access_key = secret_key,
                host=host,
                port=port,
                is_secure=False,               # uncomment if you are not using ssl
                calling_format = boto.s3.connection.OrdinaryCallingFormat(),
                )

    def get_bucket(self, bucket_name):
        return self.conn.lookup(bucket_name)

def append_attr_value(d, attr, attrv):
    if attrv and len(str(attrv)) > 0:
        d[attr] = attrv

def append_attr(d, k, attr):
    try:
        attrv = getattr(k, attr)
    except:
        return
    append_attr_value(d, attr, attrv)

def get_attrs(k, attrs):
    d = {}
    for a in attrs:
        append_attr(d, k, a)

    return d

def append_query_arg(s, n, v):
    if not v:
        return s
    nv = '{n}={v}'.format(n=n, v=v)
    if not s:
        return nv
    return '{s}&{nv}'.format(s=s, nv=nv)

class KeyJSONEncoder(boto.s3.key.Key):
    @staticmethod
    def default(k, versioned=False):
        attrs = ['name', 'size', 'last_modified', 'metadata', 'cache_control',
                 'content_type', 'content_disposition', 'content_language',
                 'owner', 'storage_class', 'md5', 'version_id', 'encrypted',
                 'delete_marker', 'expiry_date', 'VersionedEpoch', 'RgwxTag']
        d = get_attrs(k, attrs)
        d['etag'] = k.etag[1:-1]
        if versioned:
            d['is_latest'] = k.is_latest
        return d

class DeleteMarkerJSONEncoder(boto.s3.key.Key):
    @staticmethod
    def default(k):
        attrs = ['name', 'version_id', 'last_modified', 'owner']
        d = get_attrs(k, attrs)
        d['delete_marker'] = True
        d['is_latest'] = k.is_latest
        return d

class UserJSONEncoder(boto.s3.user.User):
    @staticmethod
    def default(k):
        attrs = ['id', 'display_name']
        return get_attrs(k, attrs)

class BucketJSONEncoder(boto.s3.bucket.Bucket):
    @staticmethod
    def default(k):
        attrs = ['name', 'creation_date']
        return get_attrs(k, attrs)

class BucketLifecycleRuleJSONEncoder(boto.s3.lifecycle.Rule):
    @staticmethod
    def default(k):
        attrs = ['id', 'prefix', 'status', 'expiration', 'transition']
        return get_attrs(k, attrs)

class BucketLifecycleExpirationJSONEncoder(boto.s3.lifecycle.Expiration):
    @staticmethod
    def default(k):
        attrs = ['days', 'date']
        return get_attrs(k, attrs)

class BucketLifecycleTransitionJSONEncoder(boto.s3.lifecycle.Transition):
    @staticmethod
    def default(k):
        attrs = ['days', 'date', 'storage_class']
        return get_attrs(k, attrs)

class WebsiteRedirectJSONEncoder(boto.s3.website.Redirect):
    @staticmethod
    def default(k):
        attrs = ['hostname', 'protocol', 'replace_key', 'replace_key_prefix', 'http_redirect_code']
        return get_attrs(k, attrs)

class WebsiteConditionJSONEncoder(boto.s3.website.Redirect):
    @staticmethod
    def default(k):
        attrs = ['key_prefix', 'http_error_code']
        return get_attrs(k, attrs)

class WebsiteRedirectLocationJSONEncoder(boto.s3.website.RedirectLocation):
    @staticmethod
    def default(k):
        attrs = ['hostname', 'protocol']
        return get_attrs(k, attrs)

class WebsiteRoutingRuleJSONEncoder(boto.s3.website.RoutingRule):
    @staticmethod
    def default(k):
        attrs = ['condition', 'redirect']
        return get_attrs(k, attrs)

class WebsiteConfigurationJSONEncoder(boto.s3.website.WebsiteConfiguration):
    @staticmethod
    def default(k):
        attrs = ['suffix', 'error_key', 'redirect_all_requests_to', 'routing_rules']
        return get_attrs(k, attrs)

class BotoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, boto.s3.key.Key):
            return KeyJSONEncoder.default(obj)
        if isinstance(obj, boto.s3.deletemarker.DeleteMarker):
            return DeleteMarkerJSONEncoder.default(obj)
        if isinstance(obj, boto.s3.user.User):
            return UserJSONEncoder.default(obj)
        if isinstance(obj, boto.s3.prefix.Prefix):
            return (lambda x: {'prefix': x.name})(obj)
        if isinstance(obj, boto.s3.bucket.Bucket):
            return BucketJSONEncoder.default(obj)
        if isinstance(obj, boto.s3.lifecycle.Rule):
            return BucketLifecycleRuleJSONEncoder.default(obj)
        if isinstance(obj, boto.s3.lifecycle.Expiration):
            return BucketLifecycleExpirationJSONEncoder.default(obj)
        if isinstance(obj, boto.s3.lifecycle.Transition):
            return BucketLifecycleTransitionJSONEncoder.default(obj)
        if isinstance(obj, boto.s3.website.Redirect):
            return WebsiteRedirectJSONEncoder.default(obj)
        if isinstance(obj, boto.s3.website.Condition):
            return WebsiteConditionJSONEncoder.default(obj)
        if isinstance(obj, boto.s3.website.RedirectLocation):
            return WebsiteRedirectLocationJSONEncoder.default(obj)
        if isinstance(obj, boto.s3.website.RoutingRule):
            return WebsiteRoutingRuleJSONEncoder.default(obj)
        if isinstance(obj, boto.s3.website.WebsiteConfiguration):
            return WebsiteConfigurationJSONEncoder.default(obj)
        return json.JSONEncoder.default(self, obj)

class BotoJSONEncoderListBucketVersioned(BotoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, boto.s3.key.Key):
            return KeyJSONEncoder.default(obj, versioned=True)
        return BotoJSONEncoder.default(self, obj)

def dump_json(o, cls=BotoJSONEncoder):
    return json.dumps(o, cls=cls, indent=4)


class OboBucketStatus(json.JSONEncoder):
    def default(self, k):
        if isinstance(k, boto.s3.bucket.Bucket):
            j = { 'name': k.name }
            append_attr_value(j, 'versioning_status', k.get_versioning_status())
            return j
        return json.JSONEncoder.default(self, k)

class OboBucket:
    def __init__(self, obo, args, bucket_name, need_to_exist, query_args = None):
        self.obo = obo
        self.args = args
        self.bucket_name = bucket_name
        self.bucket = obo.get_bucket(bucket_name)
        self.query_args = query_args

        if need_to_exist and not self.bucket:
            print 'ERROR: bucket does not exist:', bucket_name
            raise

    def list_objects(self):
        if (self.args.list_versions):
            l = self.bucket.get_all_versions(prefix=self.args.prefix, delimiter=self.args.delimiter,
                                        key_marker=self.args.key_marker, version_id_marker=self.args.version_id_marker,
                                        max_keys=self.args.max_keys)
            print dump_json(l, cls=BotoJSONEncoderListBucketVersioned)
        else:
            l = self.bucket.get_all_keys(prefix=self.args.prefix, delimiter=self.args.delimiter,
                                        marker=self.args.marker, max_keys=self.args.max_keys)
            print dump_json(l)

    def create(self):
        try:
            loc = self.args.location
            if not loc:
                loc = ''
            self.obo.conn.create_bucket(self.bucket_name, policy=self.args.canned_acl, location=loc)
        except socket.error as error:
            print 'Had an issue connecting: %s' % error

    def stat(self, obj):
        if obj:
            k = self.bucket.get_key(obj)
            print dump_json(k)
        else:
            print json.dumps(self.bucket, cls=OboBucketStatus, indent=4)

    def set_versioning(self, status):
        bucket = self.obo.get_bucket(self.bucket_name)
        bucket.configure_versioning(status)

    def delete_website(self):
        bucket = self.obo.get_bucket(self.bucket_name)
        bucket.delete_website_configuration()

    def get_website(self):
        bucket = self.obo.get_bucket(self.bucket_name)
        print dump_json(bucket.get_website_configuration_obj())

    def configure_website(self, suffix, error_key, redirect_all_host, redirect_all_protocol,
            condition_key_prefix, condition_http_error_code, redirect_hostname, redirect_protocol,
            redirect_replace_key, replace_key_prefix, http_redirect_code):
        bucket = self.obo.get_bucket(self.bucket_name)
        try:
            config = bucket.get_website_configuration_obj()
        except:
            config = boto.s3.website.WebsiteConfiguration()

        if suffix:
            config.suffix = suffix
        if error_key:
            config.error_key = error_key
        if redirect_all_host or redirect_all_protocol:
            config.redirect_all_requests_to = boto.s3.website.RedirectLocation(redirect_all_host, redirect_all_protocol)
        redirect_rule = None
        if condition_key_prefix or condition_http_error_code:
            redirect = boto.s3.website.Redirect(redirect_hostname, redirect_protocol, redirect_replace_key, replace_key_prefix, http_redirect_code)
            redirect_rule = boto.s3.website.RoutingRule(boto.s3.website.Condition(condition_key_prefix, condition_http_error_code), redirect)
            config.routing_rules.append(redirect_rule)

        bucket.set_website_configuration(config)

    def remove(self):
        self.obo.conn.delete_bucket(self.bucket_name)

    def getacl(self, obj):
        acl = self.bucket.get_acl(obj, version_id=self.args.version_id)
        # TODO include a better format option for importing back
        print acl

    def get(self, obj):
        k = Key(self.bucket)
        k.key = obj

        if not self.args.out_file:
            out = sys.stdout
        else:
            out = open(self.args.out_file, 'wb')

        headers = {}
        if self.args.if_modified_since:
            headers['If-Modified-Since'] = self.args.if_modified_since
        if self.args.if_unmodified_since:
            headers['If-Unmodified-Since'] = self.args.if_unmodified_since

        if self.args.date:
            headers['Date'] = self.args.date

        k.get_contents_to_file(out, version_id=self.args.version_id, headers=headers)

    def put(self, obj, meta_headers):
        k = Key(self.bucket)
        k.key = obj

        if not self.args.in_file:
            infile = sys.stdin
        else:
            infile = open(self.args.in_file, 'rb')

        reduced_redundancy = False
        if self.args.storage_class == 'REDUCED_REDUNDANCY':
            reduced_redundancy = True

        headers = meta_headers
        if self.args.content_type is not None:
            headers['Content-Type'] = self.args.content_type

        if self.args.multipart:
            part_num = 1
            part_size = self.args.part_size

            infile.seek(0, os.SEEK_END)
            file_size = infile.tell()

            mp = self.bucket.initiate_multipart_upload(obj, headers=headers)
            for offset in xrange(0, file_size, part_size):
                write_len = min(part_size, file_size - offset)
                infile.seek(offset, os.SEEK_SET)
                mp.upload_part_from_file(fp=infile, part_num=part_num, size=write_len)
                part_num += 1

            mp.complete_upload()

        else:
            k.set_contents_from_file(infile, policy=self.args.canned_acl, rewind=True, query_args=self.query_args,
                 reduced_redundancy = reduced_redundancy, headers = headers)

    def get_location(self):
        try:
            loc = self.bucket.get_location()
        except:
            loc = ''

        print dump_json(loc)

    def get_lifecycle(self):
        try:
            lc = self.bucket.get_lifecycle_config()
        except:
            lc = boto.s3.lifecycle.Lifecycle()

        print dump_json(lc)

    def add_lifecycle(self, rule_id, prefix, status_bool, expiration, transition):

        status = 'Enabled' if status_bool else 'Disabled'

        try:
            lc = self.bucket.get_lifecycle_config()
        except:
            lc = boto.s3.lifecycle.Lifecycle()

        lc.add_rule(rule_id, prefix, status, expiration, transition)

        self.bucket.configure_lifecycle(lc)

    def remove_lifecycle(self, rule_id, remove_all):

        if remove_all:
            self.bucket.delete_lifecycle_configuration()
            return

        new_lc = boto.s3.lifecycle.Lifecycle()

        try:
            lc = self.bucket.get_lifecycle_config()
        except:
            return

        for r in lc:
            if r.id != rule_id:
                new_lc.append(r) # add_rule(r.id, r.prefix, r.status, r.expiration, r.transition)

        if len(new_lc) == 0:
            self.bucket.delete_lifecycle_configuration()
            return

        self.bucket.configure_lifecycle(new_lc)


class OboObject:
    def __init__(self, obo, args, bucket_name, object_name, query_args = None):
        self.obo = obo
        self.args = args
        self.bucket_name = bucket_name
        self.bucket = obo.get_bucket(bucket_name)
        self.object_name = object_name
        self.query_args = query_args

    def remove(self, version_id, if_unmodified_since):
        query_args = append_query_arg(self.query_args, 'versionId', version_id)

        headers = {}
        if if_unmodified_since is not None:
            headers['x-amz-delete-if-unmodified-since'] = if_unmodified_since

        self.obo.conn.make_request("DELETE", bucket=self.bucket.name, key=self.object_name, query_args=query_args, headers=headers)

    def copy(self, source, version_id):
        src_str = '/{bucket}/{object}'.format(bucket=source[0], object=source[1])
        if version_id and version_id != '':
            src_str = src_str + '?versionId=' + version_id

        headers = {}
        headers['x-amz-copy-source'] = src_str

        self.obo.conn.make_request("PUT", bucket=self.bucket.name, key=self.object_name, query_args=self.query_args, headers=headers)

def next_xml_entry(attr):
    if attr.text:
        print 'attr={', attr.tag, attr.text, '}'
        return (attr.tag, attr.text)
    else:
        result = []
        for el in attr.getiterator():
            print '>', el
            result.append(dict(next_xml_entry(x) for x in el))
        return (attr.tag, None)
        #return [dict(next_xml_entry(x) for x in el) for el in attr.getchildren()]

class OboMDSearch:
    def __init__(self, obo, args, bucket_name, query, query_args = None):
        self.obo = obo
        self.args = args
        self.bucket_name = bucket_name or ''
        self.query = query
        self.query_args = query_args
        self.max_keys = args.max_keys
        self.marker = args.marker

    def search(self):
        q = self.query or ''
        query_args = append_query_arg(self.query_args, 'query', urllib.quote_plus(q))
        if self.max_keys is not None:
            query_args = append_query_arg(query_args, 'max-keys', self.max_keys)
        if self.marker is not None:
            query_args = append_query_arg(query_args, 'marker', self.marker)

        headers = {}

        result = self.obo.conn.make_request("GET", bucket=self.bucket_name, key='', query_args=query_args, headers=headers)
        if result.status == 200:
            s = result.read()
            print dump_json(xj.data(xmlfromstring(s)))
            # print dump_json([dict(next_xml_entry(attr) for attr in el) for el in et.fromstring(s)])


        else:
            print 'ERROR: http status: ' + str(result.status)
            print result.read()


class OboService:
    def __init__(self, obo, args):
        self.obo = obo
        self.args = args

    def list_buckets(self):
        print dump_json(self.obo.conn.get_all_buckets())

class OboBucketLocationCommand:
    def __init__(self, obo, args):
        self.obo = obo
        self.args = args

    def parse(self):
        parser = argparse.ArgumentParser(
            description='S3 control tool',
            usage='obo bucket location get <bucket> [<args>]')
        parser.add_argument('subcommand', help='Subcommand to run')
        # parse_args defaults to [1:] for args, but you need to
        # exclude the rest of the args too, or validation will fail
        args = parser.parse_args(self.args[0:1])
        if not hasattr(self, args.subcommand):
            print 'Unrecognized subcommand:', args.subcommand
            parser.print_help()
            exit(1)
        # use dispatch pattern to invoke method with same name
        return getattr(self, args.subcommand)

    def get(self):
        parser = argparse.ArgumentParser(
            description='Get bucket location',
            usage='obo bucket location get <bucket>')
        parser.add_argument('bucket_name')
        args = parser.parse_args(self.args[1:])

        OboBucket(self.obo, args, args.bucket_name, True).get_location()

class OboBucketLifecycleCommand:
    def __init__(self, obo, args):
        self.obo = obo
        self.args = args

    def parse(self):
        parser = argparse.ArgumentParser(
            description='S3 control tool',
            usage='obo bucket lifecycle [add | remove | get] <bucket> [<args>]')
        parser.add_argument('subcommand', help='Subcommand to run')
        # parse_args defaults to [1:] for args, but you need to
        # exclude the rest of the args too, or validation will fail
        args = parser.parse_args(self.args[0:1])
        if not hasattr(self, args.subcommand):
            print 'Unrecognized subcommand:', args.subcommand
            parser.print_help()
            exit(1)
        # use dispatch pattern to invoke method with same name
        return getattr(self, args.subcommand)

    def get(self):
        parser = argparse.ArgumentParser(
            description='Get bucket lifecycle configuration',
            usage='obo bucket lifecycle get <bucket>')
        parser.add_argument('bucket_name')
        args = parser.parse_args(self.args[1:])

        OboBucket(self.obo, args, args.bucket_name, True).get_lifecycle()

    def add(self):
        parser = argparse.ArgumentParser(
            description='Add bucket lifecycle configuration',
            usage='obo bucket lifecycle add <bucket>')
        parser.add_argument('bucket_name')
        parser.add_argument('--id')
        parser.add_argument('--prefix')
        parser.add_argument('--enable', action='store_true')
        parser.add_argument('--disable', action='store_true')
        parser.add_argument('--expiration-days')
        parser.add_argument('--expiration-date')
        parser.add_argument('--transition-days')
        parser.add_argument('--transition-date')
        parser.add_argument('--transition-storage-class')
        args = parser.parse_args(self.args[1:])

        assert args.enable != args.disable

        expiration = boto.s3.lifecycle.Expiration(args.expiration_days, args.expiration_date)
        transition = None
        if args.transition_storage_class:
            transition = boto.s3.lifecycle.Transition(args.transition_days, args.transition_date, args.transition_storage_class)

        OboBucket(self.obo, args, args.bucket_name, True).add_lifecycle(args.id, args.prefix,
                args.enable, expiration, transition)

    def remove(self):
        parser = argparse.ArgumentParser(
            description='Delete bucket lifecycle configuration',
            usage='obo bucket lifecycle remove <bucket>')
        parser.add_argument('bucket_name')
        parser.add_argument('--id')
        parser.add_argument('--remove-all', action='store_true', default=False)
        args = parser.parse_args(self.args[1:])

        OboBucket(self.obo, args, args.bucket_name, True).remove_lifecycle(args.id, args.remove_all)


class OboBucketCommand:
    def __init__(self, obo, args):
        self.obo = obo
        self.args = args

    def parse(self):
        parser = argparse.ArgumentParser(
            description='S3 control tool',
            usage='''obo bucket <subcommand> [--enable[=<true|<false>]]

The subcommands are:
   versioning                    Manipulate bucket versioning
   lifecycle                     Manipulate bucket lifecycle configuration
   website                       Manipulate bucket website configuration
''')
        parser.add_argument('subcommand', help='Subcommand to run')
        # parse_args defaults to [1:] for args, but you need to
        # exclude the rest of the args too, or validation will fail
        args = parser.parse_args(self.args[0:1])
        if not hasattr(self, args.subcommand):
            print 'Unrecognized subcommand:', args.subcommand
            parser.print_help()
            exit(1)
        # use dispatch pattern to invoke method with same name
        return getattr(self, args.subcommand)

    def versioning(self):
        parser = argparse.ArgumentParser(
            description='Get/set bucket versioning',
            usage='obo bucket versioning [bucket_name] [<args>]')
        parser.add_argument('bucket_name')
        parser.add_argument('--enable', action='store_true')
        parser.add_argument('--disable', action='store_true')
        args = parser.parse_args(self.args[1:])

        assert args.enable != args.disable

        OboBucket(self.obo, args, args.bucket_name, True).set_versioning(args.enable)

    def website(self):
        parser = argparse.ArgumentParser(
            description='Get/set/delete bucket website',
            usage='obo bucket website [bucket_name] [--set|--delete|--get] [<args>]')
        parser.add_argument('bucket_name')
        parser.add_argument('--set', action='store_true')
        parser.add_argument('--delete', action='store_true')
        parser.add_argument('--get', action='store_true')
        parser.add_argument('--suffix')
        parser.add_argument('--error-key')
        parser.add_argument('--redirect-all-host')
        parser.add_argument('--redirect-all-protocol')
        parser.add_argument('--condition-key-prefix')
        parser.add_argument('--condition-http-error-code')
        parser.add_argument('--redirect-hostname')
        parser.add_argument('--redirect-protocol')
        parser.add_argument('--redirect-replace-key')
        parser.add_argument('--redirect-replace-key-prefix')
        parser.add_argument('--http-redirect-code')
        args = parser.parse_args(self.args[1:])

        if args.set:
            OboBucket(self.obo, args, args.bucket_name, True).configure_website(args.suffix, args.error_key, args.redirect_all_host, args.redirect_all_protocol,
                    args.condition_key_prefix, args.condition_http_error_code,
                    args.redirect_hostname, args.redirect_protocol, args.redirect_replace_key, args.redirect_replace_key_prefix,
                    args.http_redirect_code)
        elif args.delete:
            OboBucket(self.obo, args, args.bucket_name, True).delete_website()
        else:
            OboBucket(self.obo, args, args.bucket_name, True).get_website()

    def lifecycle(self):
        cmd = OboBucketLifecycleCommand(self.obo, sys.argv[3:]).parse()
        cmd()

    def location(self):
        cmd = OboBucketLocationCommand(self.obo, sys.argv[3:]).parse()
        cmd()

class OboCommand:

    def _parse(self):
        parser = argparse.ArgumentParser(
            description='S3 control tool',
            usage='''obo <command> [<args>]

The commands are:
   list                          List buckets
   list <bucket>                 List objects in bucket
   getacl <bucket>[/<key>]       Get object ACL
   create <bucket>               Create a bucket
   stat <bucket>                 Get bucket info
   get <bucket>/<obj>            Get object
   put <bucket>/<obj>            Put object
   delete <bucket>[/<key>]       Delete bucket or key
   copy <source> <target>        Copies an object
   bucket versioning <bucket>    Enable/disable bucket versioning
   bucket lifecycle <...>        Manage bucket lifecycle
   bucket location get <...>     Read bucket location
   bucket website <...>          Manage bucket website
''')
        parser.add_argument('command', help='Subcommand to run')
        # parse_args defaults to [1:] for args, but you need to
        # exclude the rest of the args too, or validation will fail
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command) or args.command[0] == '_':
            print 'Unrecognized command:', args.command
            parser.print_help()
            exit(1)
        # use dispatch pattern to invoke method with same name
        ret = getattr(self, args.command)
        access_key = os.environ['S3_ACCESS_KEY_ID']
        secret_key = os.environ['S3_SECRET_ACCESS_KEY']
        host = os.environ['S3_HOSTNAME']

        self.obo = OBO(access_key, secret_key, host)
        return ret

    def _add_rgwx_parser_args(self, parser):
        parser.add_argument('--rgwx-uid')
        parser.add_argument('--rgwx-version-id')
        parser.add_argument('--rgwx-versioned-epoch')
        parser.add_argument('--rgwx-source-zone')
        parser.add_argument('--rgwx-client-id')
        parser.add_argument('--rgwx-op-id')
        parser.add_argument('--rgwx-copy-if-newer', action='store_true')

    def _get_rgwx_query_args(self, args):
        qa = append_query_arg(None, 'rgwx-uid', args.rgwx_uid)
        qa = append_query_arg(qa, 'rgwx-version-id', args.rgwx_version_id)
        qa = append_query_arg(qa, 'rgwx-versioned-epoch', args.rgwx_versioned_epoch)
        qa = append_query_arg(qa, 'rgwx-source-zone', args.rgwx_source_zone)
        qa = append_query_arg(qa, 'rgwx-client-id', args.rgwx_client_id)
        qa = append_query_arg(qa, 'rgwx-op-id', args.rgwx_op_id)
        qa = append_query_arg(qa, 'rgwx-copy-if-newer', args.rgwx_copy_if_newer)
        return qa

    def list(self):
        parser = argparse.ArgumentParser(
            description='List buckets or objects in bucket',
            usage='obo list [bucket_name] [<args>]')
        parser.add_argument('bucket_name', nargs='?')
        parser.add_argument('--versions', action='store_true')
        parser.add_argument('--prefix')
        parser.add_argument('--delimiter')
        parser.add_argument('--marker')
        parser.add_argument('--max-keys')
        parser.add_argument('--list-versions', action='store_true')
        parser.add_argument('--key-marker')
        parser.add_argument('--version-id-marker')
        args = parser.parse_args(sys.argv[2:])

        if not args.bucket_name:
            OboService(self.obo, args).list_buckets()
        else:
            OboBucket(self.obo, args, args.bucket_name, True).list_objects()

    def create(self):
        parser = argparse.ArgumentParser(
            description='Create a bucket',
            usage='obo create <bucket_name> [<args>]')
        parser.add_argument('bucket_name')
        parser.add_argument('--location')
        parser.add_argument('--canned-acl')
        args = parser.parse_args(sys.argv[2:])

        OboBucket(self.obo, args, args.bucket_name, False).create()

    def stat(self):
        parser = argparse.ArgumentParser(
            description='Get bucket status',
            usage='obo stat <target> [<args>]')
        parser.add_argument('target', help='Target of operation: <bucket>[/<object>]')
        args = parser.parse_args(sys.argv[2:])

        target = args.target.split('/', 1)

        obj = target[1] if len(target) == 2 else None

        OboBucket(self.obo, args, target[0], True).stat(obj)

    def get(self):
        parser = argparse.ArgumentParser(
            description='Get object',
            usage='obo get <bucket_name>/<key> [<args>]')
        parser.add_argument('source')
        parser.add_argument('--version-id')
        parser.add_argument('--if-modified-since')
        parser.add_argument('--if-unmodified-since')
        parser.add_argument('--date')
        parser.add_argument('-o', '--out-file')
        args = parser.parse_args(sys.argv[2:])

        target = args.source.split('/', 1)

        assert len(target) == 2

        OboBucket(self.obo, args, target[0], True).get(target[1])

    def getacl(self):
        parser = argparse.ArgumentParser(
            description='Get object',
            usage='obo getcl <bucket_name>/<key> [<args>]')
        parser.add_argument('source')
        parser.add_argument('--version-id')
        args = parser.parse_args(sys.argv[2:])

        target = args.source.split('/', 1)
        obj = target[1] if len(target) == 2 else ''

        OboBucket(self.obo, args, target[0], True).getacl(obj)

    def put(self):
        parser = argparse.ArgumentParser(
            description='Put object',
            usage='obo put <bucket_name>/<key> [<args>]')
        parser.add_argument('target')
        parser.add_argument('-i', '--in-file')
        parser.add_argument('--canned-acl')
        parser.add_argument('--content-type')
        parser.add_argument('--multipart', action='store_true')
        parser.add_argument('--part_size', type=int, default=8*1024*1024)
        parser.add_argument('--storage-class', choices = ['STANDARD', 'REDUCED_REDUNDANCY'])
        parser.add_argument('--x-amz-meta', nargs='*')
        self._add_rgwx_parser_args(parser)
        args = parser.parse_args(sys.argv[2:])

        target = args.target.split('/', 1)

        x_amz_meta = {}
        for meta in args.x_amz_meta:
            kv = meta.split('=', 1)
            if len(kv) != 2:
                continue
            x_amz_meta['X-Amz-Meta-{k}'.format(k=kv[0])] = kv[1]


        rgwx_query_args = self._get_rgwx_query_args(args)

        assert len(target) == 2

        OboBucket(self.obo, args, target[0], True, query_args=rgwx_query_args).put(target[1], x_amz_meta)

    def delete(self):
        parser = argparse.ArgumentParser(
            description='Delete a bucket or an object',
            usage='obo delete <target> [<args>]')
        parser.add_argument('target')
        parser.add_argument('--version-id')
        parser.add_argument('--if-unmodified-since')
        self._add_rgwx_parser_args(parser)
        args = parser.parse_args(sys.argv[2:])

        target = args.target.split('/', 1)

        rgwx_query_args = self._get_rgwx_query_args(args)

        if len(target) == 1:
            OboBucket(self.obo, args, target[0], False).remove()
        else:
            assert len(target) == 2
            OboObject(self.obo, args, target[0], target[1], query_args=rgwx_query_args).remove(args.version_id, args.if_unmodified_since)

    def copy(self):
        parser = argparse.ArgumentParser(
            description='Copies an object',
            usage='obo copy <source> <target> [<args>]')
        parser.add_argument('source')
        parser.add_argument('target')
        parser.add_argument('--version-id')
        self._add_rgwx_parser_args(parser)
        args = parser.parse_args(sys.argv[2:])

        source = args.source.split('/', 1)
        target = args.target.split('/', 1)

        rgwx_query_args = self._get_rgwx_query_args(args)

        OboObject(self.obo, args, target[0], target[1], query_args=rgwx_query_args).copy(source, args.version_id)

    def mdsearch(self):
        parser = argparse.ArgumentParser(
            description='Performs metadata search',
            usage='obo mdsearch [bucket] --query=<query>')
        parser.add_argument('bucket', nargs='?')
        parser.add_argument('--query')
        parser.add_argument('--max-keys')
        parser.add_argument('--marker')
        self._add_rgwx_parser_args(parser)
        args = parser.parse_args(sys.argv[2:])

        rgwx_query_args = self._get_rgwx_query_args(args)

        OboMDSearch(self.obo, args, args.bucket, args.query, query_args=rgwx_query_args).search()

    def bucket(self):
        cmd = OboBucketCommand(self.obo, sys.argv[2:]).parse()
        cmd()

def main():
    cmd = OboCommand()._parse()
    cmd()


