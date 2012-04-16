//
// Copyright (C) 2011-2012 Andrey Sibiryov <me@kobology.ru>
//
// Licensed under the BSD 2-Clause License (the "License");
// you may not use this file except in compliance with the License.
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

#ifndef COCAINE_DEALER_PYTHON_BINDING_RESPONSE_OBJECT_HPP
#define COCAINE_DEALER_PYTHON_BINDING_RESPONSE_OBJECT_HPP

// NOTE: These are being redefined in Python.h
#undef _POSIX_C_SOURCE
#undef _XOPEN_SOURCE

#include "Python.h"

#include <boost/shared_ptr.hpp>

namespace cocaine { namespace dealer {

class response;

class response_wrapper_t {
    public:
        explicit response_wrapper_t(const boost::shared_ptr<response>& response_):
            m_response(response_)
        { }

        response* operator -> () {
            return m_response.get();
        }

    private:
        boost::shared_ptr<response> m_response;
};

class response_object_t {
    public:
        PyObject_HEAD

        static PyObject* constructor(PyTypeObject * type, PyObject * args, PyObject * kwargs);
        static int initializer(response_object_t * self, PyObject * args, PyObject * kwargs);
        static void destructor(response_object_t * self);

        static PyObject* get(response_object_t * self, PyObject * args, PyObject * kwargs);

        static PyObject* iter_next(response_object_t * it);

    public:
        response_wrapper_t * m_future;
};

static PyMethodDef response_object_methods[] = {
    { "get", (PyCFunction)response_object_t::get, METH_KEYWORDS,
        "Pulls in a response chunk." },
    { NULL, NULL, 0, NULL }
};

static PyTypeObject response_object_type = {
    PyObject_HEAD_INIT(&PyType_Type)
    0,                                          /* ob_size */
    "cocaine.client.Response",                  /* tp_name */
    sizeof(response_object_t),                  /* tp_basicsize */
    0,                                          /* tp_itemsize */
    (destructor)response_object_t::destructor,  /* tp_dealloc */
    0,                                          /* tp_print */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
    0,                                          /* tp_compare */
    0,                                          /* tp_repr */
    0,                                          /* tp_as_number */
    0,                                          /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    0,                                          /* tp_hash */
    0,                                          /* tp_call */
    0,                                          /* tp_str */
    0,                                          /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT,                         /* tp_flags */
    "Deferred Response",                        /* tp_doc */
    0,                                          /* tp_traverse */
    0,                                          /* tp_clear */
    0,                                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    PyObject_SelfIter,                          /* tp_iter */
    (iternextfunc)response_object_t::iter_next, /* tp_iternext */
    response_object_methods,                    /* tp_methods */
    0,                                          /* tp_members */
    0,                                          /* tp_getset */
    0,                                          /* tp_base */
    0,                                          /* tp_dict */
    0,                                          /* tp_descr_get */
    0,                                          /* tp_descr_set */
    0,                                          /* tp_dictoffset */
    (initproc)response_object_t::initializer,   /* tp_init */
    0,                                          /* tp_alloc */
    response_object_t::constructor              /* tp_new */
};

}}
#endif