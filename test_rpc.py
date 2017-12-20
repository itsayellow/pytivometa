#!/usr/bin/env python3

import rpcSearch103
import pprint
import json

PP = pprint.PrettyPrinter(indent=4)

with open('test_rpc.conf', 'r') as conf_fh:
    conf_data = json.loads(conf_fh.read())

mind_remote = rpcSearch103.Remote(
        conf_data['username'],
        conf_data['password']
        )

# -----------------------------------------------------------------------------
# Reference

print("-"*78)
print("Reference")
print("""results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Friends",
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        levelOfDetail='medium',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        )
""")
print("")

results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Friends",
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        levelOfDetail='medium',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        )
PP.pprint(results)

# -----------------------------------------------------------------------------
# levelOfDetail='low',

print("-"*78)
print("levelOfDetail='low'")
print("""results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Friends",
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        levelOfDetail='low',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        )
""")
print("")

results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Friends",
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        levelOfDetail='low',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        )
PP.pprint(results)

# -----------------------------------------------------------------------------
# levelOfDetail='high',

print("-"*78)
print("levelOfDetail='high'")
print("""results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Friends",
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        levelOfDetail='high',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        )
""")
print("")

results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Friends",
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        levelOfDetail='high',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        )
PP.pprint(results)

# -----------------------------------------------------------------------------
# levelOfDetail='high', collectionType='series',

print("-"*78)
print("levelOfDetail='high', collectionType='series',")
print("""results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Friends",
        collectionType='series',
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        levelOfDetail='high',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
)""")
print("")

results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Friends",
        collectionType='series',
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        levelOfDetail='high',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        )
PP.pprint(results)

# -----------------------------------------------------------------------------
# levelOfDetail='high', collectionType='movie',

print("-"*78)
print("levelOfDetail='high', collectionType='movie',")
print("""results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Children of a Lesser God",
        collectionType='movie',
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        levelOfDetail='high',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        )
""")
print("")

results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Children of a Lesser God",
        collectionType='movie',
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        levelOfDetail='high',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        )
PP.pprint(results)

# -----------------------------------------------------------------------------
# levelOfDetail='high', collectionType='movie',

print("-"*78)
print("levelOfDetail='high', collectionType='movie',")
print("""results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Children of a Lesser God",
        collectionType='movie',
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        levelOfDetail='high',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        )
""")
print("")

resp_template = [
        ]
results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Children of a Lesser God",
        collectionType='movie',
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        levelOfDetail='high',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        )
PP.pprint(results)

# -----------------------------------------------------------------------------
# responseTemplate, collectionType='series',

print("-"*78)
print("responseTemplate, collectionType='series',")
print("""
resp_template = [
        {
            'type': 'responseTemplate',
            'fieldName': ['collection'],
            'typeName': 'collectionList'
            },
        {
            'type': 'responseTemplate',
            'fieldName': ['collectionId','title','partnerCollectionId',
                'description','descriptionLanguage'],
            'typeName': 'collection'
            },
        ]
results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Friends",
        collectionType='series',
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        responseTemplate=resp_template,
        )
""")
print("")

resp_template = [
        {
            'type': 'responseTemplate',
            'fieldName': ['collection'],
            'typeName': 'collectionList'
            },
        {
            'type': 'responseTemplate',
            'fieldName': ['collectionId','title','partnerCollectionId',
                'description','descriptionLanguage'],
            'typeName': 'collection'
            },
        ]
results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Friends",
        collectionType='series',
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        responseTemplate=resp_template,
        )
PP.pprint(results)

# -----------------------------------------------------------------------------
# responseTemplate, collectionType='series',

print("-"*78)
print("responseTemplate, collectionType='series', descriptionLanguage=['English','English GB']")
print("""
resp_template = [
        {
            'type': 'responseTemplate',
            'fieldName': ['collection'],
            'typeName': 'collectionList'
            },
        {
            'type': 'responseTemplate',
            'fieldName': ['collectionId','title','partnerCollectionId',
                'description','descriptionLanguage'],
            'typeName': 'collection'
            },
        ]
results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Friends",
        collectionType='series',
        count=10,
        descriptionLanguage=['English','English GB'],
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        responseTemplate=resp_template,
        )
""")
print("")

resp_template = [
        {
            'type': 'responseTemplate',
            'fieldName': ['collection'],
            'typeName': 'collectionList'
            },
        {
            'type': 'responseTemplate',
            'fieldName': ['collectionId','title','partnerCollectionId',
                'description','descriptionLanguage'],
            'typeName': 'collection'
            },
        ]
results = mind_remote.rpc_req_generic(
        'collectionSearch',
        keyword="Friends",
        collectionType='series',
        count=10,
        descriptionLanguage=['English','English GB'],
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        responseTemplate=resp_template,
        )
PP.pprint(results)

# -----------------------------------------------------------------------------
# responseTemplate, collectionId='tivo:cl.16645',

print("-"*78)
print("responseTemplate, collectionType='series',")
print("""
resp_template = [
        {
            'type': 'responseTemplate',
            'fieldName': ['collection'],
            'typeName': 'collectionList'
            },
        {
            'type': 'responseTemplate',
            'fieldName': [
                'category',
                'collectionId',
                'credit',
                'title',
                'partnerCollectionId',
                'description',
                'descriptionLanguage',
                'episodic',
                'internalRating',
                'rating',
                'tvRating'
                ],
            'typeName': 'collection'
            },
        {
            'type': 'responseTemplate',
            'fieldName': [
                'categoryId',
                'displayRank',
                'label',
                'topLevel',
                ],
            'typeName': 'category'
            },
        {
            'type': 'responseTemplate',
            'fieldName': [
                'personId',
                'role',
                'last',
                'first',
                'characterName',
                'fullName',
                ],
            'typeName': 'credit'
            },
        ]
results = mind_remote.rpc_req_generic(
        'collectionSearch',
        collectionId='tivo:cl.16645',
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        responseTemplate=resp_template,
        )
""")
print("")

resp_template = [
        {
            'type': 'responseTemplate',
            'fieldName': ['collection'],
            'typeName': 'collectionList'
            },
        {
            'type': 'responseTemplate',
            'fieldName': [
                'category',
                'collectionId',
                'credit',
                'title',
                'partnerCollectionId',
                'description',
                'descriptionLanguage',
                'episodic',
                'internalRating',
                'rating',
                'tvRating'
                ],
            'typeName': 'collection'
            },
        {
            'type': 'responseTemplate',
            'fieldName': [
                'categoryId',
                'displayRank',
                'label',
                'topLevel',
                ],
            'typeName': 'category'
            },
        {
            'type': 'responseTemplate',
            'fieldName': [
                'personId',
                'role',
                'last',
                'first',
                'characterName',
                'fullName',
                ],
            'typeName': 'credit'
            },
        ]
results = mind_remote.rpc_req_generic(
        'collectionSearch',
        collectionId='tivo:cl.16645',
        count=10,
        filterUnavailable='false',
        includeBroadcast='true',
        includeFree='true',
        includePaid='false',
        includeVod='false',
        mergeOverridingCollections='true',
        orderBy='strippedTitle',
        responseTemplate=resp_template,
        )
PP.pprint(results)

