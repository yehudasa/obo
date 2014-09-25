import sys
import os
import boto
import boto.s3.connection
import argparse
import json


class OBO:
    def __init__(self, access_key, secret_key, host):
        self.conn = boto.connect_s3(
                aws_access_key_id = access_key,
                aws_secret_access_key = secret_key,
                host = 'skinny',
                is_secure=False,               # uncomment if you are not using ssl
                calling_format = boto.s3.connection.OrdinaryCallingFormat(),
                )

    def get_bucket(self, bucket_name):
        return self.conn.lookup(bucket_name)

    def set_bucket_versioning(self, bucket_name, status):
        bucket = self.get_bucket(bucket_name)
        bucket.configure_versioning(status)

def append_attr(d, k, attr):
    attrv = getattr(k, attr)
    if attrv and len(str(attrv)) > 0:
        d[attr] = attrv

def get_attrs(k, attrs):
    d = {}
    for a in attrs:
        append_attr(d, k, a)

    return d

class KeyJSONEncoder(boto.s3.key.Key):
    @staticmethod
    def default(k):
        attrs = ['name', 'size', 'last_modified', 'metadata', 'cache_control',
                 'content_type', 'content_disposition', 'content_language',
                 'etag', 'owner', 'storage_class', 'md5', 'version_id', 'encrypted']
        return get_attrs(k, attrs)
    
class UserJSONEncoder(boto.s3.user.User):
    @staticmethod
    def default(k):
        attrs = ['id', 'display_name']
        return get_attrs(k, attrs)
 
class BotoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, boto.s3.key.Key):
            return KeyJSONEncoder.default(obj)
        if isinstance(obj, boto.s3.user.User):
            return UserJSONEncoder.default(obj)
        return json.JSONEncoder.default(self, obj)

def dump_json(o):
    return json.dumps(obj, cls=BotoJSONEncoder, indent=4)

class OboBucket:
    def __init__(self, obo, bucket_name, need_to_exist):
        self.obo = obo
        self.bucket_name = bucket_name
        self.bucket = obo.get_bucket(bucket_name)

        if need_to_exist and not self.bucket:
            print 'ERROR: bucket does not exist:', bucket_name
            raise

    def list_objects(self):
        print json.dumps(self.bucket.get_all_keys(), cls=BotoJSONEncoder, indent=4)

    def set_versioning(self, status):
        bucket = obo.get_bucket(self.obo, self.bucket_name)
        bucket.configure_versioning(status)


class OboCommand:

    def __init__(self, obo):
        self.obo = obo
        parser = argparse.ArgumentParser(
            description='S3 control tool',
            usage='''obo <command> [<args>]

The commands are:
   list       List objects in bucket
''')
        parser.add_argument('command', help='Subcommand to run')
        # parse_args defaults to [1:] for args, but you need to
        # exclude the rest of the args too, or validation will fail
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print 'Unrecognized command'
            parser.print_help()
            exit(1)
        # use dispatch pattern to invoke method with same name
        getattr(self, args.command)()

    def list(self):
        parser = argparse.ArgumentParser(
            description='List objects in bucket')
        parser.add_argument('bucket_name')
        parser.add_argument('--versions', action='store_true')
        args = parser.parse_args(sys.argv[2:])

        ob = OboBucket(self.obo, args.bucket_name, True)

        ob.list_objects()


def main():
    access_key = os.environ['S3_ACCESS_KEY_ID']
    secret_key = os.environ['S3_SECRET_ACCESS_KEY']
    host = os.environ['S3_HOSTNAME']

    obo = OBO(access_key, secret_key, host)

    cmd = OboCommand(obo)

    bucket_name = sys.argv[1]

    # obo.set_bucket_versioning(bucket_name = sys.argv[1], status = True)

